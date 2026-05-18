# ScreenViewer - WiFi Screen Sharing Application

ScreenViewer es una aplicación multiplataforma diseñada para iOS y Android que permite la recepción, visualización y gestión remota de flujos de pantalla mediante conexión inalámbrica. El sistema elimina la dependencia de interfaces físicas por cable mediante la implementación de protocolos de transmisión de bajo retardo, ofreciendo una experiencia estable para entornos profesionales, educativos y de soporte técnico.

## Características

- 📡 **Conexión WiFi**: Transmisión de pantalla sin cables
- ⚡ **Bajo Retardo**: Protocolo optimizado para mínima latencia
- 🗜️ **Compresión**: Datos comprimidos para mejor rendimiento
- 🔒 **Verificación**: Checksum CRC32 para integridad de datos
- 📊 **Estadísticas en Tiempo Real**: FPS, latencia y uso de datos
- 🖥️ **Multi-monitor**: Soporte para múltiples monitores
- 👥 **Múltiples Clientes**: Hasta 5 clientes simultáneos

## Arquitectura

```
┌─────────────────┐         WiFi          ┌─────────────────┐
│     SERVER      │ ◄───────────────────► │     CLIENT      │
│                 │      TCP:5050         │                 │
│  - Captura      │                       │  - Recibe       │
│  - Comprime     │                       │  - Descomprime  │
│  - Envía        │                       │  - Muestra      │
└─────────────────┘                       └─────────────────┘
```

## Requisitos

### Python 3.7+

**Dependencias del Servidor:**
```bash
pip install mss pillow
```

**Dependencias del Cliente:**
```bash
pip install pillow
```

## Instalación

1. Clonar o descargar el proyecto:
```bash
cd screenviewer
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

## Uso

### Iniciar el Servidor (en la máquina con la pantalla a compartir)

```bash
# Modo básico
python server/server.py

# Con opciones personalizadas
python server/server.py --host 0.0.0.0 --port 5050 --monitor 1 --max-clients 5
```

**Opciones del servidor:**
- `--host`: Dirección IP para escuchar (default: 0.0.0.0)
- `--port`: Puerto TCP (default: 5050)
- `--monitor`: ID del monitor a capturar (default: 1)
- `--max-clients`: Máximo de clientes simultáneos (default: 5)

### Conectar el Cliente (en el dispositivo receptor)

```bash
# Con interfaz gráfica
python client/client.py <IP_DEL_SERVIDOR>

# Ejemplo
python client/client.py 192.168.1.100

# Sin GUI (solo estadísticas)
python client/client.py 192.168.1.100 --no-gui

# Con puerto personalizado
python client/client.py 192.168.1.100 --port 5050
```

## Ejemplo de Sesión

### Terminal 1 - Servidor:
```bash
$ python server/server.py
============================================================
ScreenViewer Server Started
============================================================
Listening on: 0.0.0.0:5050
Local IP: 192.168.1.100
Max clients: 5
Monitor: 1
============================================================

Clients can connect to: 192.168.1.100:5050

Press Ctrl+C to stop

[+] Client connected: ('192.168.1.50', 54321)
[+] Active clients: 1
```

### Terminal 2 - Cliente:
```bash
$ python client/client.py 192.168.1.100
[+] Connected to 192.168.1.100:5050
[+] Server acknowledged connection
Resolution: 1920x1080

ScreenViewer Client Started
========================================
```

## Protocolo de Comunicación

El protocolo utiliza TCP sobre WiFi con el siguiente formato de mensaje:

```
┌─────────┬───────┬────────────┬──────────────┐
│  Type   │ Flags │ Sequence   │    Size      │
│ (1 byte)│(1 byte)│ (4 bytes) │  (4 bytes)   │
└─────────┴───────┴────────────┴──────────────┘
│                                          │
└────────────── Payload ───────────────────┘
```

**Tipos de Mensaje:**
- `HELLO` (1): Saludo inicial del cliente
- `HELLO_ACK` (2): Confirmación del servidor
- `SCREEN_DATA` (3): Datos de frame de pantalla
- `SCREEN_ACK` (4): Confirmación de recepción
- `DISCONNECT` (5): Solicitud de desconexión
- `HEARTBEAT` (6): Señal de mantenimiento

## Estructura del Proyecto

```
screenviewer/
├── common/
│   └── __init__.py      # Utilidades compartidas
├── server/
│   └── server.py        # Servidor de captura
├── client/
│   └── client.py        # Cliente visualizador
├── requirements.txt     # Dependencias
└── README.md           # Este archivo
```

## Rendimiento

- **FPS Objetivo**: 30 FPS
- **Latencia Típica**: 50-200ms (dependiendo de la red WiFi)
- **Compresión**: zlib nivel 6
- **Resolución**: Automática según el monitor

## Solución de Problemas

### El cliente no puede conectar
1. Verificar que ambos dispositivos están en la misma red WiFi
2. Verificar que el firewall permite el puerto 5050
3. Confirmar la IP correcta del servidor

### Bajo rendimiento
1. Reducir la resolución del monitor
2. Acercar los dispositivos al router WiFi
3. Usar WiFi 5GHz en lugar de 2.4GHz

### Error de dependencias
```bash
pip install --upgrade pip
pip install mss pillow
```

## Limitaciones

- Requiere que ambos dispositivos estén en la misma red WiFi
- El rendimiento depende de la calidad de la red inalámbrica
- No incluye cifrado (para uso en redes confiables)

## Futuras Mejoras

- [ ] Cifrado SSL/TLS
- [ ] Compresión más eficiente (H.264)
- [ ] Control remoto del escritorio
- [ ] Aplicación móvil nativa (iOS/Android)
- [ ] Descubrimiento automático de servidores
- [ ] Grabación de sesiones

## Licencia

MIT License - Uso libre para fines educativos y comerciales.

## Autor

Desarrollado como demostración de aplicación de streaming de pantalla sobre WiFi.
