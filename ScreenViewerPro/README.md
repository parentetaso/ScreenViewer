# 📺 ScreenViewer Pro

Aplicación de transmisión de pantalla por WiFi con interfaz gráfica moderna.

## ✨ Características

- **Interfaz Gráfica Moderna**: Diseño oscuro con gradientes y animaciones
- **Configuración Completa desde Menús**: 
  - Resolución (1920x1080, 1280x720, etc.)
  - Calidad JPEG (50%-95%)
  - Límite de FPS (15-60 o ilimitado)
  - Puerto personalizado
- **Sin Comandos**: Todo desde botones y menús desplegables
- **Compatible con Cualquier Dispositivo**: 
  - iPhone: Abre Safari → http://[IP]:5050
  - Android: Abre Chrome → http://[IP]:5050
  - PC/Mac: Cualquier navegador web

## 🚀 Instalación Rápida (Windows)

### Opción A: Ejecutable Directo (Recomendado)

1. **Doble clic en** `crear_ejecutable.bat`
2. Espera a que termine la instalación
3. Encuentra `ScreenViewerPro.exe` en la carpeta `dist/`
4. **¡Listo!** Doble clic para usar siempre

### Opción B: Ejecutar desde Python

```bash
pip install -r requirements.txt
python main.py
```

## 📱 Cómo Usar

### En tu PC Windows:

1. Abre `ScreenViewerPro.exe` (doble clic)
2. Configura desde los menús desplegables:
   - 📐 Resolución deseada
   - 🎨 Calidad de imagen
   - ⚡ FPS máximos
   - 🔌 Puerto (default: 5050)
3. Presiona **"▶ INICIAR TRANSMISIÓN"**
4. Anota la IP que aparece (ej: `192.168.1.50:5050`)

### En tu iPhone/Android:

1. Conéctate al mismo WiFi que tu PC
2. Abre **Safari** (iPhone) o **Chrome** (Android)
3. Escribe la IP que muestra la PC: `http://192.168.1.50:5050`
4. ¡Verás la pantalla de tu PC en tiempo real!

## ⚠️ Nota sobre AirPlay

Este programa **NO usa AirPlay** (protocolo propietario de Apple). 

**Solución:** Usa el navegador de tu iPhone (Safari) para acceder a la URL que muestra la PC. Funciona igual de bien y es compatible con todos los dispositivos.

## 🛠️ Requisitos

- Windows 10/11
- Python 3.8+ (solo para crear el ejecutable)
- Conexión WiFi (misma red para PC y celular)

## 📁 Estructura

```
ScreenViewerPro/
├── main.py                 # Aplicación principal
├── requirements.txt        # Dependencias
├── crear_ejecutable.bat    # Crea el .exe automáticamente
├── README.md              # Este archivo
└── dist/
    └── ScreenViewerPro.exe  # Ejecutable final
```

---

**Hecho con ❤️ para transmisión fácil por WiFi**
