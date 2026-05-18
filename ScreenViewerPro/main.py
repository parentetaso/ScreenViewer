import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import socket
import threading
import json
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
from PIL import Image, ImageGrab
import io

# Configuración Global
CONFIG_FILE = "config_screenviewer.json"
DEFAULT_PORT = 5050

class StreamHandler(BaseHTTPRequestHandler):
    """Servidor Web para transmisión compatible con navegadores móviles"""
    server_instance = None
    
    def log_message(self, format, *args):
        pass  # Silenciar logs en consola
        
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html = self.get_html_page()
            self.wfile.write(html.encode())
        elif self.path.startswith("/stream"):
            self.handle_stream()
        else:
            self.send_response(404)
            self.end_headers()

    def get_html_page(self):
        return """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ScreenViewer Pro</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white; font-family: 'Segoe UI', sans-serif;
            display: flex; flex-direction: column; align-items: center;
            min-height: 100vh; padding: 20px;
        }
        .header { text-align: center; margin-bottom: 20px; }
        h1 { color: #00d2ff; font-size: 2em; text-shadow: 0 0 10px rgba(0,210,255,0.5); }
        .status { color: #00ff88; font-size: 0.9em; margin-top: 5px; }
        .screen-container {
            width: 100%; max-width: 800px;
            background: #0f0f1a; border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5), 0 0 20px rgba(0,210,255,0.2);
            overflow: hidden; border: 2px solid #00d2ff;
        }
        #screen { width: 100%; display: block; }
        .controls { margin-top: 20px; display: flex; gap: 10px; }
        button {
            background: #00d2ff; color: #1a1a2e; border: none;
            padding: 12px 25px; border-radius: 25px; font-weight: bold;
            cursor: pointer; transition: all 0.3s;
        }
        button:hover { transform: scale(1.05); box-shadow: 0 0 15px rgba(0,210,255,0.6); }
        .info { margin-top: 20px; text-align: center; color: #888; font-size: 0.85em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📺 ScreenViewer Pro</h1>
        <div class="status">● En vivo desde tu PC</div>
    </div>
    <div class="screen-container">
        <img id="screen" src="/stream" alt="Cargando pantalla..." />
    </div>
    <div class="controls">
        <button onclick="location.reload()">🔄 Recargar</button>
        <button onclick="toggleFullscreen()">⛶ Pantalla Completa</button>
    </div>
    <div class="info">
        Toque la pantalla para interactuar<br>
        Actualización automática cada 100ms
    </div>
    <script>
        function toggleFullscreen() {
            const img = document.getElementById('screen');
            if (img.requestFullscreen) img.requestFullscreen();
        }
        // Auto-refresh simple
        let lastUpdate = 0;
        setInterval(() => {
            const img = document.getElementById('screen');
            img.src = '/stream?t=' + Date.now();
        }, 100);
    </script>
</body>
</html>
        """

    def handle_stream(self):
        if self.server_instance and self.server_instance.latest_frame:
            self.send_response(200)
            self.send_header("Content-type", "image/jpeg")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(self.server_instance.latest_frame)
        else:
            # Imagen por defecto si no hay frame
            img = Image.new('RGB', (800, 600), color=(20, 20, 40))
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80)
            self.send_response(200)
            self.send_header("Content-type", "image/jpeg")
            self.end_headers()
            self.wfile.write(buf.getvalue())

class ScreenViewerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("ScreenViewer Pro - Transmisión WiFi")
        self.geometry("1000x750")
        self.minsize(900, 650)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        self.is_running = False
        self.http_server = None
        self.server_thread = None
        self.latest_frame = None
        self.capture_thread = None
        self.running_flag = True
        
        self.config = self.load_config()
        
        self.setup_ui()
        self.get_local_ip()
        
    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color="#1a1a2e")
        self.sidebar.grid(row=0, column=0, sticky="ns")
        
        # Título
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_frame.pack(pady=30)
        ctk.CTkLabel(title_frame, text="📺", font=ctk.CTkFont(size=40)).pack()
        ctk.CTkLabel(title_frame, text="ScreenViewer", font=ctk.CTkFont(size=22, weight="bold"), text_color="#00d2ff").pack()
        ctk.CTkLabel(title_frame, text="PRO", font=ctk.CTkFont(size=14), text_color="#00ff88").pack()
        
        # Configuración
        settings_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        settings_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Resolución
        ctk.CTkLabel(settings_frame, text="📐 Resolución", anchor="w", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=(15,5))
        self.res_menu = ctk.CTkOptionMenu(settings_frame, values=["1920x1080", "1280x720", "800x600", "Original"], 
                                          command=lambda x: self.save_setting("resolution", x))
        self.res_menu.set(self.config.get("resolution", "1280x720"))
        self.res_menu.pack(padx=10, pady=5, fill="x")
        
        # Calidad
        ctk.CTkLabel(settings_frame, text="🎨 Calidad", anchor="w", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=(15,5))
        self.qual_menu = ctk.CTkOptionMenu(settings_frame, values=["Alta (95%)", "Media (85%)", "Baja (70%)", "Mínima (50%)"],
                                           command=lambda x: self.save_setting("quality", x))
        self.qual_menu.set(self.config.get("quality", "Media (85%)"))
        self.qual_menu.pack(padx=10, pady=5, fill="x")
        
        # FPS
        ctk.CTkLabel(settings_frame, text="⚡ FPS Máximo", anchor="w", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=(15,5))
        self.fps_menu = ctk.CTkOptionMenu(settings_frame, values=["60 FPS", "30 FPS", "24 FPS", "15 FPS", "Ilimitado"],
                                          command=lambda x: self.save_setting("fps", x))
        self.fps_menu.set(self.config.get("fps", "30 FPS"))
        self.fps_menu.pack(padx=10, pady=5, fill="x")
        
        # Puerto
        ctk.CTkLabel(settings_frame, text="🔌 Puerto", anchor="w", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=(15,5))
        self.port_entry = ctk.CTkEntry(settings_frame, placeholder_text="5050")
        self.port_entry.insert(0, str(self.config.get("port", 5050)))
        self.port_entry.pack(padx=10, pady=5, fill="x")
        
        # Botón Principal
        self.btn_toggle = ctk.CTkButton(self.sidebar, text="▶ INICIAR TRANSMISIÓN", 
                                        height=60, font=ctk.CTkFont(size=18, weight="bold"),
                                        fg_color="#00d2ff", text_color="#1a1a2e",
                                        hover_color="#00aacc", corner_radius=15,
                                        command=self.toggle_server)
        self.btn_toggle.pack(padx=20, pady=30, fill="x")
        
        # Estado
        self.status_box = ctk.CTkFrame(self.sidebar, fg_color="#0f0f1a", corner_radius=10)
        self.status_box.pack(padx=20, pady=10, fill="x")
        
        self.lbl_status = ctk.CTkLabel(self.status_box, text="● Detenido", text_color="#ff4444", 
                                       font=ctk.CTkFont(weight="bold"))
        self.lbl_status.pack(pady=10)
        
        self.lbl_ip = ctk.CTkLabel(self.status_box, text="IP: --.--.--.--", text_color="#888",
                                   font=ctk.CTkFont(family="Consolas", size=12))
        self.lbl_ip.pack(pady=5)
        
        self.lbl_clients = ctk.CTkLabel(self.status_box, text="Clientes: 0", text_color="#888")
        self.lbl_clients.pack(pady=5)
        
        # Área Principal
        self.main_area = ctk.CTkFrame(self, corner_radius=15, fg_color="#0f0f1a")
        self.main_area.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.canvas = ctk.CTkCanvas(self.main_area, bg="#1a1a2e", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.canvas.create_text(450, 300, text="🖥️\nEsperando inicio de transmisión...\n\n" +
                                "Una vez iniciado, abre en tu celular:\n" +
                                "http://[TU-IP]:5050", 
                                fill="#444", font=("Arial", 16), justify="center")
        
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
        
    def save_setting(self, key, value):
        self.config[key] = value
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f)
            
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            port = self.port_entry.get()
            self.lbl_ip.configure(text=f"IP: {ip}:{port}")
            return ip
        except:
            self.lbl_ip.configure(text="IP: Sin conexión")
            return "0.0.0.0"
            
    def toggle_server(self):
        if not self.is_running:
            self.start_server()
        else:
            self.stop_server()
            
    def start_server(self):
        ip = self.get_local_ip()
        if ip == "0.0.0.0":
            messagebox.showwarning("Sin Red", "No se detectó conexión de red.")
            return
            
        port = int(self.port_entry.get())
        self.is_running = True
        self.running_flag = True
        
        self.btn_toggle.configure(text="⏹ DETENER TRANSMISIÓN", fg_color="#ff4444", hover_color="#cc0000", text_color="white")
        self.lbl_status.configure(text="● Transmitiendo", text_color="#00ff88")
        
        # Iniciar captura de pantalla
        self.capture_thread = threading.Thread(target=self.capture_screen, daemon=True)
        self.capture_thread.start()
        
        # Iniciar servidor HTTP
        StreamHandler.server_instance = self
        
        def run_server():
            try:
                self.http_server = HTTPServer((ip, port), StreamHandler)
                print(f"Servidor iniciado en http://{ip}:{port}")
                self.http_server.serve_forever()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo iniciar: {e}")
                
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
    def stop_server(self):
        self.is_running = False
        self.running_flag = False
        
        self.btn_toggle.configure(text="▶ INICIAR TRANSMISIÓN", fg_color="#00d2ff", hover_color="#00aacc", text_color="#1a1a2e")
        self.lbl_status.configure(text="● Detenido", text_color="#ff4444")
        
        if self.http_server:
            self.http_server.shutdown()
            
        self.latest_frame = None
        self.canvas.delete("all")
        self.canvas.create_text(450, 300, text="🖥️\nTransmisión detenida\n\nListo para reiniciar", 
                                fill="#444", font=("Arial", 16), justify="center")
        
    def capture_screen(self):
        fps_limit = self.fps_menu.get()
        quality_str = self.qual_menu.get()
        quality = int(quality_str.split("(")[1].replace("%)", ""))
        
        delay = 0
        if fps_limit != "Ilimitado":
            fps = int(fps_limit.replace(" FPS", ""))
            delay = 1.0 / fps
            
        while self.running_flag:
            start_time = time.time()
            try:
                screenshot = ImageGrab.grab()
                buffer = io.BytesIO()
                screenshot.save(buffer, format='JPEG', quality=quality)
                self.latest_frame = buffer.getvalue()
                
                # Actualizar canvas (en hilo principal sería mejor, pero esto es demo)
                # Por simplicidad, no actualizamos el canvas local en tiempo real
                
            except Exception as e:
                print(f"Error capturando: {e}")
                
            if delay > 0:
                elapsed = time.time() - start_time
                sleep_time = delay - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
    def on_closing(self):
        self.running_flag = False
        if self.http_server:
            self.http_server.shutdown()
        self.destroy()

if __name__ == "__main__":
    app = ScreenViewerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
