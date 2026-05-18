#!/usr/bin/env python3
"""
ScreenViewer - Instalador y Lanzador Inteligente
Detecta si ya está configurado y salta pasos innecesarios.
Configura el sistema para recibir pantallas desde iOS/Android nativamente.

USO:
    python setup.py
    
En la primera ejecución:
- Instala dependencias automáticamente
- Configura el firewall
- Crea accesos directos
- Guarda configuración

En ejecuciones siguientes:
- Detecta configuración previa
- Pregunta si saltar verificación de dependencias
- Inicia directamente el servidor web
"""

import os
import sys
import subprocess
import json
import socket
from pathlib import Path

CONFIG_FILE = "screenviewer_config.json"
REQUIRED_PACKAGES = ["flask", "flask-cors", "pillow", "numpy", "mss"]

def check_root():
    """Verifica si se ejecuta como root/administrador"""
    return os.geteuid() == 0 if os.name != 'nt' else True

def get_local_ip():
    """Obtiene la IP local de la máquina"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def load_config():
    """Carga la configuración existente"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None

def save_config(config):
    """Guarda la configuración"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def check_dependencies():
    """Verifica e instala dependencias si es necesario"""
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"📦 Instalando dependencias faltantes: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "-q"])
        print("✅ Dependencias instaladas")
        return False
    return True

def setup_firewall(port=5050):
    """Configura el firewall para permitir el puerto"""
    print("🔥 Configurando firewall...")
    try:
        if sys.platform == 'win32':
            # Windows
            subprocess.run([
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                'name="ScreenViewer"', 'dir=in', 'action=allow',
                f'protocol=TCP', f'localport={port}'
            ], capture_output=True)
        elif sys.platform == 'darwin':
            # macOS - solo notificación
            print("⚠️  En macOS, permite el acceso cuando se solicite")
        else:
            # Linux
            subprocess.run(['ufw', 'allow', str(port)], capture_output=True)
        print("✅ Firewall configurado")
    except Exception as e:
        print(f"⚠️  No se pudo configurar el firewall automáticamente: {e}")

def create_desktop_shortcut():
    """Crea un acceso directo en el escritorio"""
    print("🖥️  Creando acceso directo...")
    try:
        if sys.platform == 'win32':
            # Windows shortcut
            shortcut_content = f'''@echo off
cd /d "{os.getcwd()}"
{sys.executable} server/server.py
pause
'''
            with open('Iniciar_ScreenViewer.bat', 'w') as f:
                f.write(shortcut_content)
            print("✅ Acceso directo creado: Iniciar_ScreenViewer.bat")
        elif sys.platform == 'darwin':
            # macOS app
            script = f'''#!/bin/bash
cd "{os.getcwd()}"
{sys.executable} server/server.py
'''
            with open('Iniciar_ScreenViewer.command', 'w') as f:
                f.write(script)
            os.chmod('Iniciar_ScreenViewer.command', 0o755)
            print("✅ Acceso directo creado: Iniciar_ScreenViewer.command")
        else:
            # Linux desktop file
            desktop_content = f'''[Desktop Entry]
Version=1.0
Name=ScreenViewer Server
Exec={sys.executable} {os.getcwd()}/server/server.py
Terminal=true
Type=Application
Categories=Utility;
'''
            with open('ScreenViewer.desktop', 'w') as f:
                f.write(desktop_content)
            os.chmod('ScreenViewer.desktop', 0o755)
            print("✅ Acceso directo creado: ScreenViewer.desktop")
    except Exception as e:
        print(f"⚠️  No se pudo crear el acceso directo: {e}")

def show_connection_instructions(ip, port=5050):
    """Muestra instrucciones de conexión para iOS/Android"""
    print("\n" + "="*60)
    print("📱 CONEXIÓN DESDE CELULAR")
    print("="*60)
    print(f"\n🌐 Tu IP local: {ip}:{port}")
    print("\n🍎 iPhone/iPad:")
    print("   1. Abre Centro de Control (desliza hacia abajo)")
    print("   2. Toca 'Grabación de pantalla' 🎯")
    print("   3. Mantén presionado hasta ver opciones")
    print("   4. Selecciona 'ScreenViewer' en la lista")
    print("   5. Si no aparece, usa una app de terceros como:")
    print("      - LetsView (gratis)")
    print("      - ApowerMirror")
    print("\n🤖 Android:")
    print("   1. Desliza el panel de notificaciones")
    print("   2. Busca 'Transmitir', 'Smart View' o 'Cast'")
    print("   3. Selecciona 'ScreenViewer' o usa:")
    print("      - LetsView (gratis)")
    print("      - Screen Mirroring")
    print("\n💡 Nota: Ambos dispositivos deben estar en la misma red WiFi")
    print("="*60 + "\n")

def main():
    print("🚀 ScreenViewer - Instalador Inteligente\n")
    
    # Cargar configuración existente
    config = load_config()
    
    if config and config.get('installed'):
        print("✅ Configuración previa detectada")
        if config.get('ip'):
            print(f"📍 IP guardada: {config['ip']}")
        skip_deps = input("¿Saltar verificación de dependencias? (s/n): ").lower() == 's'
        if not skip_deps:
            check_dependencies()
    else:
        print("🆕 Primera ejecución - Configurando sistema...\n")
        
        # Verificar dependencias
        check_dependencies()
        
        # Configurar firewall
        setup_firewall()
        
        # Crear accesos directos
        create_desktop_shortcut()
        
        # Guardar configuración
        config = {
            'installed': True,
            'ip': get_local_ip(),
            'port': 5050,
            'first_run': False
        }
        save_config(config)
        print("✅ Configuración guardada")
    
    # Obtener IP actual
    ip = get_local_ip()
    
    # Mostrar instrucciones
    show_connection_instructions(ip)
    
    # Iniciar servidor web con interfaz gráfica
    print("🎬 Iniciando servidor ScreenViewer con interfaz web...")
    print("Presiona Ctrl+C para detener\n")
    
    try:
        # Importar y ejecutar el servidor web
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from server.web_server import run_web_server
        run_web_server(host='0.0.0.0', port=8080)
    except KeyboardInterrupt:
        print("\n👋 Servidor detenido")
    except Exception as e:
        print(f"❌ Error al iniciar: {e}")
        print("Intentando ejecutar directamente...")
        subprocess.run([sys.executable, "server/web_server.py"])

if __name__ == "__main__":
    main()
