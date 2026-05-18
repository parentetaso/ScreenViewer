#!/usr/bin/env python3
"""
ScreenViewer - Aplicación de Escritorio con GUI Moderna
Compatible con Windows, macOS y Linux
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import socket
import threading
import json
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

# Configuración inicial
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ScreenViewerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configuración de ventana
        self.title("📱 ScreenViewer - Transmisión por WiFi")
        self.geometry("900x700")
        self.minsize(800, 600)
        
        # Variables de estado
        self.server_running = False
        self.server_thread = None
        self.clients = []
        self.stats = {"fps": 0, "total_frames": 0, "start_time": None}
        self.config_file = Path.home() / "screenviewer_config.json"
        
        # Cargar configuración guardada
        self.load_config()
        
        # Crear interfaz
        self.create_widgets()
        
        # Obtener IP local
        self.local_ip = self.get_local_ip()
        self.update_status_display()
        
        # Verificar si es primera vez
        self.check_first_run()
    
    def get_local_ip(self):
        """Obtiene la IP local de la máquina"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def load_config(self):
        """Carga configuración guardada"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except:
                self.config = {}
        else:
            self.config = {}
    
    def save_config(self):
        """Guarda configuración"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def check_first_run(self):
        """Verifica si es la primera ejecución"""
        if not self.config.get('setup_complete', False):
            messagebox.showinfo(
                "👋 Bienvenido a ScreenViewer",
                "¡Es tu primera vez!\n\n"
                "1. Haz clic en 'INICIAR SERVIDOR'\n"
                "2. En tu iPhone: Centro de Control → Grabación de pantalla\n"
                "3. En tu Android: Panel → Transmitir/Smart View\n"
                "4. Selecciona esta computadora\n\n"
                "La aplicación recordará tu configuración."
            )
            self.config['setup_complete'] = True
            self.config['first_run_date'] = datetime.now().isoformat()
            self.save_config()
    
    def create_widgets(self):
        """Crea todos los widgets de la interfaz"""
        
        # Frame principal con padding
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 20))
        
        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="📱 ScreenViewer",
            font=ctk.CTkFont(size=32, weight="bold")
        )
        self.title_label.pack(side="left")
        
        self.subtitle_label = ctk.CTkLabel(
            self.header_frame,
            text="Transmisión de Pantalla por WiFi",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.subtitle_label.pack(side="left", padx=20, pady=10)
        
        # Panel de estado
        self.status_frame = ctk.CTkFrame(self.main_frame)
        self.status_frame.pack(fill="x", pady=10)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="● DETENIDO",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#FF6B6B"
        )
        self.status_label.pack(pady=10)
        
        self.ip_label = ctk.CTkLabel(
            self.status_frame,
            text=f"IP de este equipo: {self.local_ip}",
            font=ctk.CTkFont(size=14)
        )
        self.ip_label.pack(pady=5)
        
        # Botón principal
        self.start_button = ctk.CTkButton(
            self.main_frame,
            text="🚀 INICIAR SERVIDOR",
            font=ctk.CTkFont(size=20, weight="bold"),
            height=60,
            command=self.toggle_server,
            fg_color="#4CAF50",
            hover_color="#45a049"
        )
        self.start_button.pack(fill="x", pady=20)
        
        # Panel de estadísticas
        self.stats_frame = ctk.CTkFrame(self.main_frame)
        self.stats_frame.pack(fill="both", expand=True, pady=10)
        
        self.stats_title = ctk.CTkLabel(
            self.stats_frame,
            text="📊 Estadísticas en Tiempo Real",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.stats_title.pack(pady=10)
        
        # Grid de estadísticas
        self.stats_grid = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        self.stats_grid.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.stats_grid.grid_columnconfigure(0, weight=1)
        self.stats_grid.grid_columnconfigure(1, weight=1)
        
        # FPS
        self.fps_label = ctk.CTkLabel(
            self.stats_grid,
            text="FPS\n--",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#4ECDC4"
        )
        self.fps_label.grid(row=0, column=0, pady=10, padx=10)
        
        # Clientes
        self.clients_label = ctk.CTkLabel(
            self.stats_grid,
            text="Dispositivos\n0 conectados",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#FFE66D"
        )
        self.clients_label.grid(row=0, column=1, pady=10, padx=10)
        
        # Frames totales
        self.frames_label = ctk.CTkLabel(
            self.stats_grid,
            text="Frames\n0",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#FF6B6B"
        )
        self.frames_label.grid(row=1, column=0, pady=10, padx=10)
        
        # Tiempo activo
        self.uptime_label = ctk.CTkLabel(
            self.stats_grid,
            text="Tiempo Activo\n00:00:00",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#95E1D3"
        )
        self.uptime_label.grid(row=1, column=1, pady=10, padx=10)
        
        # Lista de dispositivos
        self.devices_frame = ctk.CTkFrame(self.main_frame)
        self.devices_frame.pack(fill="both", expand=True, pady=10)
        
        self.devices_title = ctk.CTkLabel(
            self.devices_frame,
            text="📱 Dispositivos Conectados",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.devices_title.pack(pady=10)
        
        self.devices_listbox = ctk.CTkTextbox(
            self.devices_frame,
            font=ctk.CTkFont(size=12),
            state="disabled"
        )
        self.devices_listbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Instrucciones
        self.instructions_frame = ctk.CTkFrame(self.main_frame, fg_color="#2b2b2b")
        self.instructions_frame.pack(fill="x", pady=10)
        
        instructions_text = """
🍎 iPhone: Desliza desde arriba-derecha → Toca 📱 Grabación de pantalla → Selecciona esta PC
🤖 Android: Desliza panel → Busca 'Transmitir', 'Smart View' o 'Cast' → Selecciona esta PC
💡 Nota: Ambos dispositivos deben estar en la misma red WiFi
        """
        
        self.instructions_label = ctk.CTkLabel(
            self.instructions_frame,
            text=instructions_text.strip(),
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        self.instructions_label.pack(padx=20, pady=15)
        
        # Footer
        self.footer_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.footer_frame.pack(fill="x", pady=(10, 0))
        
        self.version_label = ctk.CTkLabel(
            self.footer_frame,
            text="v2.0 | Hecho con ❤️ para iOS y Android",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        self.version_label.pack(side="right")
        
        # Actualizar estadísticas periódicamente
        self.update_stats_loop()
    
    def toggle_server(self):
        """Inicia o detiene el servidor"""
        if self.server_running:
            self.stop_server()
        else:
            self.start_server()
    
    def start_server(self):
        """Inicia el servidor de ScreenViewer"""
        try:
            # Importar servidor
            from server.server import ScreenViewerServer
            
            self.server = ScreenViewerServer(host='0.0.0.0', port=5050)
            self.server_running = True
            
            # Iniciar en hilo separado
            self.server_thread = threading.Thread(target=self.run_server, daemon=True)
            self.server_thread.start()
            
            # Actualizar UI
            self.start_button.configure(
                text="⏹ DETENER SERVIDOR",
                fg_color="#FF6B6B",
                hover_color="#ff5252"
            )
            self.status_label.configure(
                text="● EN EJECUCIÓN",
                text_color="#4CAF50"
            )
            
            self.stats["start_time"] = time.time()
            
            messagebox.showinfo(
                "✅ Servidor Iniciado",
                f"📡 ScreenViewer está corriendo\n\n"
                f"🌐 IP: {self.local_ip}\n"
                f"🔌 Puerto: 5050\n\n"
                f"Ahora conecta tu celular desde:\n"
                f"• iPhone: Centro de Control → Grabación\n"
                f"• Android: Panel → Transmitir/Smart View"
            )
            
        except Exception as e:
            messagebox.showerror("❌ Error", f"No se pudo iniciar el servidor:\n{str(e)}")
            self.server_running = False
    
    def run_server(self):
        """Ejecuta el servidor en segundo plano"""
        try:
            self.server.start()
        except Exception as e:
            print(f"Error en servidor: {e}")
    
    def stop_server(self):
        """Detiene el servidor"""
        try:
            if hasattr(self, 'server'):
                self.server.stop()
            
            self.server_running = False
            
            # Actualizar UI
            self.start_button.configure(
                text="🚀 INICIAR SERVIDOR",
                fg_color="#4CAF50",
                hover_color="#45a049"
            )
            self.status_label.configure(
                text="● DETENIDO",
                text_color="#FF6B6B"
            )
            
            self.clients = []
            self.stats = {"fps": 0, "total_frames": 0, "start_time": None}
            self.update_stats_display()
            
        except Exception as e:
            messagebox.showerror("❌ Error", f"No se pudo detener el servidor:\n{str(e)}")
    
    def update_stats_loop(self):
        """Actualiza las estadísticas periódicamente"""
        if self.server_running:
            # Calcular uptime
            if self.stats["start_time"]:
                elapsed = time.time() - self.stats["start_time"]
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.uptime_label.configure(text=f"Tiempo Activo\n{uptime_str}")
            
            # Simular estadísticas (en implementación real vendrían del servidor)
            if self.stats["start_time"]:
                self.stats["fps"] = max(0, min(60, self.stats.get("fps", 0)))
                self.stats["total_frames"] += self.stats.get("fps", 0)
            
            self.update_stats_display()
        
        # Llamar de nuevo en 1 segundo
        self.after(1000, self.update_stats_loop)
    
    def update_stats_display(self):
        """Actualiza la visualización de estadísticas"""
        self.fps_label.configure(text=f"FPS\n{self.stats.get('fps', 0)}")
        self.clients_label.configure(
            text=f"Dispositivos\n{len(self.clients)} conectados"
        )
        self.frames_label.configure(text=f"Frames\n{self.stats.get('total_frames', 0)}")
    
    def update_status_display(self):
        """Actualiza la información de estado"""
        self.ip_label.configure(text=f"IP de este equipo: {self.local_ip}")


def main():
    """Función principal"""
    app = ScreenViewerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
