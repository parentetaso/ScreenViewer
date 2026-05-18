#!/usr/bin/env python3
"""
ScreenViewer - Servidor Web con Interfaz Gráfica Moderna
Permite conexión desde iOS/Android mediante el menú nativo de compartir pantalla
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import threading
import socket
import struct
import time
import json
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Set

try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import (
    MessageType, MessageHeader, HEADER_SIZE,
    compress_data, get_local_ip, BUFFER_SIZE
)

app = Flask(__name__)
CORS(app)

# Estado global del servidor
server_state = {
    'running': False,
    'clients': [],
    'fps': 0,
    'resolution': (0, 0),
    'start_time': None,
    'total_frames': 0
}


class ScreenCapture:
    """Handles screen capture functionality"""
    
    def __init__(self, monitor_id: int = 1):
        self.monitor_id = monitor_id
        self.sct = None
        if MSS_AVAILABLE:
            self.sct = mss.mss()
    
    def capture_frame(self) -> Optional[bytes]:
        """Capture current screen frame as RGB bytes"""
        if not MSS_AVAILABLE or self.sct is None:
            return self._generate_test_pattern()
        
        try:
            monitor = self.sct.monitors[self.monitor_id]
            screenshot = self.sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            return img.tobytes()
        except Exception as e:
            print(f"Capture error: {e}")
            return self._generate_test_pattern()
    
    def _generate_test_pattern(self) -> bytes:
        """Generate a test pattern for demonstration"""
        width, height = 640, 480
        pixels = bytearray(width * height * 3)
        
        for y in range(height):
            for x in range(width):
                idx = (y * width + x) * 3
                pixels[idx] = int((x / width) * 255)
                pixels[idx + 1] = int((y / height) * 255)
                pixels[idx + 2] = 128
        
        return bytes(pixels)
    
    def get_resolution(self) -> tuple:
        """Get screen resolution"""
        if MSS_AVAILABLE and self.sct:
            try:
                monitor = self.sct.monitors[self.monitor_id]
                return (monitor["width"], monitor["height"])
            except:
                pass
        return (640, 480)


class ClientHandler(threading.Thread):
    """Handles communication with a single client"""
    
    def __init__(self, conn: socket.socket, addr: tuple, screen_capture: ScreenCapture):
        super().__init__()
        self.conn = conn
        self.addr = addr
        self.screen_capture = screen_capture
        self.running = True
        self.sequence = 0
        self.fps_limit = 30
        self.frames_sent = 0
        self.start_time = time.time()
    
    def run(self):
        """Main client handling loop"""
        print(f"[+] Client connected: {self.addr}")
        
        # Update global state
        server_state['clients'].append({
            'ip': self.addr[0],
            'port': self.addr[1],
            'connected_at': datetime.now().isoformat(),
            'frames': 0
        })
        
        try:
            self._send_message(MessageType.HELLO_ACK, b'')
            
            width, height = self.screen_capture.get_resolution()
            res_data = struct.pack("!II", width, height)
            self._send_message(MessageType.SCREEN_DATA, res_data, flags=1)
            
            frame_interval = 1.0 / self.fps_limit
            last_frame_time = time.time()
            
            while self.running:
                current_time = time.time()
                
                self._check_messages()
                
                if current_time - last_frame_time >= frame_interval:
                    self._send_frame()
                    last_frame_time = current_time
                    self.frames_sent += 1
                    server_state['total_frames'] += 1
                
                # Update FPS every second
                elapsed = current_time - self.start_time
                if elapsed > 0:
                    self.fps_limit = min(60, max(15, int(self.frames_sent / elapsed)))
                
                time.sleep(0.001)
                
        except Exception as e:
            print(f"[-] Client {self.addr} error: {e}")
        finally:
            self._cleanup()
    
    def _check_messages(self):
        """Check for incoming messages from client"""
        self.conn.setblocking(False)
        try:
            header_data = self.conn.recv(HEADER_SIZE)
            if len(header_data) == HEADER_SIZE:
                header = MessageHeader.unpack(header_data)
                if header.msg_type == MessageType.DISCONNECT:
                    self.running = False
                elif header.msg_type == MessageType.HEARTBEAT:
                    self._send_message(MessageType.HEARTBEAT, b'')
        except BlockingIOError:
            pass
        except Exception:
            pass
        finally:
            self.conn.setblocking(True)
    
    def _send_frame(self):
        """Capture and send a screen frame"""
        frame = self.screen_capture.capture_frame()
        if frame:
            compressed = compress_data(frame)
            timestamp = int(time.time() * 1000)
            checksum = sum(frame) & 0xFFFFFFFF
            metadata = struct.pack("!IIQ", self.sequence, timestamp, checksum)
            payload = metadata + compressed
            self._send_message(MessageType.SCREEN_DATA, payload)
            self.sequence += 1
    
    def _send_message(self, msg_type: MessageType, data: bytes, flags: int = 0):
        """Send a message with header"""
        header = MessageHeader(msg_type=msg_type, flags=flags, 
                              sequence=self.sequence, size=len(data))
        header_bytes = header.pack()
        self.conn.sendall(header_bytes + data)
    
    def _cleanup(self):
        """Clean up client connection"""
        try:
            self.conn.close()
        except:
            pass
        
        # Remove from global state
        server_state['clients'] = [c for c in server_state['clients'] 
                                   if c['ip'] != self.addr[0] or c['port'] != self.addr[1]]
        
        print(f"[-] Client disconnected: {self.addr}")


class ScreenViewerServer:
    """Main server class that manages connections"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 5050, 
                 monitor_id: int = 1, max_clients: int = 5):
        self.host = host
        self.port = port
        self.monitor_id = monitor_id
        self.max_clients = max_clients
        self.server_socket: Optional[socket.socket] = None
        self.clients: Set[ClientHandler] = set()
        self.screen_capture = ScreenCapture(monitor_id)
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the server in a background thread"""
        if self.running:
            return
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.max_clients)
            self.server_socket.settimeout(1.0)
            
            server_state['running'] = True
            server_state['start_time'] = datetime.now().isoformat()
            server_state['resolution'] = self.screen_capture.get_resolution()
            
            self.running = True
            self.thread = threading.Thread(target=self._accept_loop, daemon=True)
            self.thread.start()
            
            print(f"✅ Streaming server started on port {self.port}")
            
        except Exception as e:
            print(f"Server error: {e}")
            self.stop()
    
    def _accept_loop(self):
        """Accept incoming client connections"""
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                
                if len(self.clients) >= self.max_clients:
                    print(f"[-] Rejecting {addr}: max clients reached")
                    conn.close()
                    continue
                
                handler = ClientHandler(conn, addr, self.screen_capture)
                handler.daemon = True
                handler.start()
                self.clients.add(handler)
                
                print(f"[+] Active clients: {len(self.clients)}")
                
            except socket.timeout:
                self.clients = {c for c in self.clients if c.is_alive()}
                # Update FPS
                if server_state['start_time']:
                    start = datetime.fromisoformat(server_state['start_time'])
                    elapsed = (datetime.now() - start).total_seconds()
                    if elapsed > 0:
                        server_state['fps'] = round(server_state['total_frames'] / elapsed, 1)
            except Exception as e:
                if self.running:
                    print(f"Accept error: {e}")
    
    def stop(self):
        """Stop the server"""
        self.running = False
        
        for client in list(self.clients):
            client.running = False
            try:
                client.conn.close()
            except:
                pass
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        server_state['running'] = False
        server_state['clients'] = []
        print("❌ Streaming server stopped")


# Instancia global del servidor
stream_server = None


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📺 ScreenViewer - Transmisión por WiFi</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 900px;
            width: 100%;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 1.1em;
        }
        
        .content {
            padding: 30px;
        }
        
        .status-card {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 25px;
        }
        
        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid #e9ecef;
        }
        
        .status-row:last-child {
            border-bottom: none;
        }
        
        .status-label {
            font-weight: 600;
            color: #495057;
        }
        
        .status-value {
            font-size: 1.2em;
            font-weight: bold;
            color: #667eea;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
        }
        
        .status-indicator.active {
            background: #28a745;
            box-shadow: 0 0 10px #28a745;
        }
        
        .status-indicator.inactive {
            background: #dc3545;
        }
        
        .btn {
            display: inline-block;
            padding: 15px 30px;
            font-size: 1.1em;
            font-weight: 600;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            text-decoration: none;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
        }
        
        .btn-group {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 20px;
        }
        
        .instructions {
            background: #e7f3ff;
            border-left: 4px solid #667eea;
            padding: 20px;
            border-radius: 10px;
            margin-top: 25px;
        }
        
        .instructions h3 {
            color: #667eea;
            margin-bottom: 15px;
        }
        
        .instructions ol {
            margin-left: 20px;
            color: #495057;
        }
        
        .instructions li {
            margin: 10px 0;
            line-height: 1.6;
        }
        
        .platform-icon {
            font-size: 1.5em;
            margin-right: 10px;
        }
        
        .client-list {
            margin-top: 20px;
        }
        
        .client-item {
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .client-info {
            display: flex;
            align-items: center;
        }
        
        .client-ip {
            font-weight: 600;
            color: #495057;
        }
        
        .client-time {
            font-size: 0.9em;
            color: #6c757d;
            margin-left: 10px;
        }
        
        .no-clients {
            text-align: center;
            color: #6c757d;
            padding: 20px;
        }
        
        .ip-display {
            background: #2d3748;
            color: #68d391;
            padding: 20px;
            border-radius: 10px;
            font-family: 'Courier New', monospace;
            font-size: 1.5em;
            text-align: center;
            margin: 20px 0;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .live-indicator {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📺 ScreenViewer</h1>
            <p>Transmisión de pantalla por WiFi para iOS y Android</p>
        </div>
        
        <div class="content">
            <div class="status-card">
                <div class="status-row">
                    <span class="status-label">
                        <span class="status-indicator" id="statusIndicator"></span>
                        Estado del Servidor
                    </span>
                    <span class="status-value" id="serverStatus">Detenido</span>
                </div>
                
                <div class="status-row">
                    <span class="status-label">Dirección IP</span>
                    <span class="status-value" id="serverIP">-</span>
                </div>
                
                <div class="status-row">
                    <span class="status-label">Puerto de Streaming</span>
                    <span class="status-value" id="serverPort">5050</span>
                </div>
                
                <div class="status-row">
                    <span class="status-label">Resolución</span>
                    <span class="status-value" id="resolution">-</span>
                </div>
                
                <div class="status-row">
                    <span class="status-label">FPS Promedio</span>
                    <span class="status-value" id="avgFps">0</span>
                </div>
                
                <div class="status-row">
                    <span class="status-label">Clientes Conectados</span>
                    <span class="status-value" id="clientCount">0</span>
                </div>
                
                <div class="status-row">
                    <span class="status-label">Total de Frames</span>
                    <span class="status-value" id="totalFrames">0</span>
                </div>
            </div>
            
            <div class="ip-display" id="connectionInfo">
                🔴 Inicia el servidor para ver la dirección de conexión
            </div>
            
            <div class="btn-group">
                <button class="btn btn-primary" id="startBtn" onclick="toggleServer()">
                    ▶️ Iniciar Servidor
                </button>
            </div>
            
            <div class="client-list" id="clientList">
                <h3 style="margin: 20px 0 10px 0; color: #495057;">📱 Dispositivos Conectados</h3>
                <div class="no-clients" id="noClientsMsg">
                    No hay dispositivos conectados actualmente
                </div>
            </div>
            
            <div class="instructions">
                <h3>📲 Cómo conectar tu celular:</h3>
                <ol>
                    <li>
                        <strong><span class="platform-icon">🍎</span>iPhone/iPad:</strong>
                        <br>Abre Centro de Control → Toca "Grabación de pantalla" 🎯 → 
                        Mantén presionado → Selecciona "ScreenViewer" o usa la app <strong>LetsView</strong>
                    </li>
                    <li>
                        <strong><span class="platform-icon">🤖</span>Android:</strong>
                        <br>Desliza el panel → Busca "Transmitir", "Smart View" o "Cast" → 
                        Selecciona "ScreenViewer" o usa <strong>LetsView</strong>
                    </li>
                    <li>
                        <strong>💡 Importante:</strong> Ambos dispositivos deben estar en la misma red WiFi
                    </li>
                </ol>
            </div>
        </div>
    </div>
    
    <script>
        let serverRunning = false;
        
        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update status indicator
                const indicator = document.getElementById('statusIndicator');
                const statusText = document.getElementById('serverStatus');
                
                if (data.running) {
                    indicator.className = 'status-indicator active live-indicator';
                    statusText.textContent = 'En Vivo 🔴';
                    document.getElementById('startBtn').textContent = '⏹️ Detener Servidor';
                    document.getElementById('startBtn').className = 'btn btn-danger';
                } else {
                    indicator.className = 'status-indicator inactive';
                    statusText.textContent = 'Detenido';
                    document.getElementById('startBtn').textContent = '▶️ Iniciar Servidor';
                    document.getElementById('startBtn').className = 'btn btn-primary';
                }
                
                // Update other fields
                document.getElementById('serverIP').textContent = data.ip || '-';
                document.getElementById('serverPort').textContent = data.port || '5050';
                document.getElementById('resolution').textContent = 
                    data.resolution ? `${data.resolution[0]}x${data.resolution[1]}` : '-';
                document.getElementById('avgFps').textContent = data.fps || '0';
                document.getElementById('clientCount').textContent = data.clients?.length || '0';
                document.getElementById('totalFrames').textContent = data.total_frames || '0';
                
                // Update connection info
                const connInfo = document.getElementById('connectionInfo');
                if (data.running && data.ip) {
                    connInfo.innerHTML = `🟢 Conecta desde: <strong>${data.ip}:${data.port}</strong>`;
                    connInfo.style.background = '#2d3748';
                    connInfo.style.color = '#68d391';
                } else {
                    connInfo.innerHTML = '🔴 Inicia el servidor para ver la dirección de conexión';
                    connInfo.style.background = '#2d3748';
                    connInfo.style.color = '#fc8181';
                }
                
                // Update client list
                const clientList = document.getElementById('clientList');
                const noClientsMsg = document.getElementById('noClientsMsg');
                
                if (data.clients && data.clients.length > 0) {
                    noClientsMsg.style.display = 'none';
                    
                    // Remove old client items (keep the title)
                    const oldItems = clientList.querySelectorAll('.client-item');
                    oldItems.forEach(item => item.remove());
                    
                    data.clients.forEach(client => {
                        const item = document.createElement('div');
                        item.className = 'client-item';
                        item.innerHTML = `
                            <div class="client-info">
                                <span class="status-indicator active"></span>
                                <span class="client-ip">${client.ip}:${client.port}</span>
                                <span class="client-time">desde ${new Date(client.connected_at).toLocaleTimeString()}</span>
                            </div>
                            <span style="color: #667eea;">📱</span>
                        `;
                        clientList.appendChild(item);
                    });
                } else {
                    noClientsMsg.style.display = 'block';
                }
                
            } catch (error) {
                console.error('Error fetching status:', error);
            }
        }
        
        async function toggleServer() {
            try {
                const endpoint = serverRunning ? '/api/stop' : '/api/start';
                await fetch(endpoint, { method: 'POST' });
                serverRunning = !serverRunning;
                updateStatus();
            } catch (error) {
                console.error('Error toggling server:', error);
                alert('Error al controlar el servidor');
            }
        }
        
        // Update status every 2 seconds
        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Render the main interface"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/status')
def get_status():
    """Get current server status"""
    return jsonify({
        'running': server_state['running'],
        'ip': get_local_ip(),
        'port': 5050,
        'fps': server_state['fps'],
        'resolution': server_state['resolution'],
        'clients': server_state['clients'],
        'total_frames': server_state['total_frames'],
        'start_time': server_state['start_time']
    })


@app.route('/api/start', methods=['POST'])
def start_server():
    """Start the streaming server"""
    global stream_server
    
    if not server_state['running']:
        stream_server = ScreenViewerServer(host='0.0.0.0', port=5050)
        stream_server.start()
        return jsonify({'success': True, 'message': 'Server started'})
    
    return jsonify({'success': False, 'message': 'Server already running'})


@app.route('/api/stop', methods=['POST'])
def stop_server():
    """Stop the streaming server"""
    global stream_server
    
    if stream_server:
        stream_server.stop()
        return jsonify({'success': True, 'message': 'Server stopped'})
    
    return jsonify({'success': False, 'message': 'Server not running'})


def run_web_server(host='0.0.0.0', port=8080):
    """Run the web interface"""
    print("\n" + "="*60)
    print("🚀 ScreenViewer - Servidor Web Iniciado")
    print("="*60)
    print(f"\n🌐 Abre tu navegador en: http://{get_local_ip()}:{port}")
    print(f"   O localmente en: http://localhost:{port}")
    print("\n📱 Desde tu celular:")
    print("   1. Asegúrate de estar en la misma red WiFi")
    print("   2. Abre la URL que aparece arriba")
    print("   3. Presiona 'Iniciar Servidor'")
    print("   4. Usa el menú nativo de tu celular para transmitir")
    print("\n" + "="*60 + "\n")
    
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    run_web_server()
