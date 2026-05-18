"""
ScreenViewer Server - Captures and streams screen data over WiFi

This server captures screen frames from the host machine and streams them
to connected clients over a WiFi network using TCP with compression.
"""

import socket
import struct
import time
import threading
import argparse
from typing import Dict, Optional, Set
from datetime import datetime

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

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import (
    MessageType, MessageHeader, HEADER_SIZE,
    compress_data, get_local_ip, BUFFER_SIZE
)


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
            # Fallback: generate test pattern if mss not available
            return self._generate_test_pattern()
        
        try:
            monitor = self.sct.monitors[self.monitor_id]
            screenshot = self.sct.grab(monitor)
            
            # Convert to RGB format
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
                # Create gradient pattern
                pixels[idx] = int((x / width) * 255)      # R
                pixels[idx + 1] = int((y / height) * 255)  # G
                pixels[idx + 2] = 128                       # B
        
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
        self.fps_limit = 30  # Target FPS
    
    def run(self):
        """Main client handling loop"""
        print(f"[+] Client connected: {self.addr}")
        
        try:
            # Send hello acknowledgment
            self._send_message(MessageType.HELLO_ACK, b'')
            
            # Send resolution info
            width, height = self.screen_capture.get_resolution()
            res_data = struct.pack("!II", width, height)
            self._send_message(MessageType.SCREEN_DATA, res_data, flags=1)
            
            # Main streaming loop
            frame_interval = 1.0 / self.fps_limit
            last_frame_time = time.time()
            
            while self.running:
                current_time = time.time()
                
                # Check for incoming messages
                self._check_messages()
                
                # Send frame if enough time has passed
                if current_time - last_frame_time >= frame_interval:
                    self._send_frame()
                    last_frame_time = current_time
                
                time.sleep(0.001)  # Small sleep to prevent CPU hogging
                
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
            # Compress the frame
            compressed = compress_data(frame)
            
            # Add metadata: sequence number, timestamp, checksum
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
    
    def start(self):
        """Start the server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(self.max_clients)
            self.server_socket.settimeout(1.0)
            
            local_ip = get_local_ip()
            print("=" * 60)
            print("ScreenViewer Server Started")
            print("=" * 60)
            print(f"Listening on: {self.host}:{self.port}")
            print(f"Local IP: {local_ip}")
            print(f"Max clients: {self.max_clients}")
            print(f"Monitor: {self.monitor_id}")
            print("=" * 60)
            print(f"\nClients can connect to: {local_ip}:{self.port}")
            print("\nPress Ctrl+C to stop\n")
            
            self.running = True
            self._accept_loop()
            
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
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
                
                # Create and start client handler
                handler = ClientHandler(conn, addr, self.screen_capture)
                handler.daemon = True
                handler.start()
                self.clients.add(handler)
                
                print(f"[+] Active clients: {len(self.clients)}")
                
            except socket.timeout:
                # Clean up finished threads
                self.clients = {c for c in self.clients if c.is_alive()}
            except Exception as e:
                if self.running:
                    print(f"Accept error: {e}")
    
    def stop(self):
        """Stop the server"""
        self.running = False
        
        # Close all client connections
        for client in list(self.clients):
            client.running = False
            try:
                client.conn.close()
            except:
                pass
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        print("Server stopped")


def main():
    parser = argparse.ArgumentParser(description='ScreenViewer Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5050, help='Port to listen on')
    parser.add_argument('--monitor', type=int, default=1, help='Monitor ID to capture')
    parser.add_argument('--max-clients', type=int, default=5, help='Maximum clients')
    
    args = parser.parse_args()
    
    # Check dependencies
    if not MSS_AVAILABLE:
        print("Warning: mss library not installed. Using test pattern.")
        print("Install with: pip install mss pillow")
    elif not PIL_AVAILABLE:
        print("Warning: Pillow not installed. Using test pattern.")
        print("Install with: pip install pillow")
    
    server = ScreenViewerServer(
        host=args.host,
        port=args.port,
        monitor_id=args.monitor,
        max_clients=args.max_clients
    )
    
    server.start()


if __name__ == '__main__':
    main()
