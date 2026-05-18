"""
ScreenViewer Client - Receives and displays screen streams over WiFi

This client connects to a ScreenViewer server and displays the received
screen frames in real-time using a graphical interface.
"""

import socket
import struct
import time
import threading
import argparse
import sys
from typing import Optional, Tuple
from datetime import datetime

try:
    import tkinter as tk
    from PIL import Image, ImageTk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import (
    MessageType, MessageHeader, HEADER_SIZE,
    decompress_data, get_local_ip, BUFFER_SIZE
)


class ScreenViewerClient:
    """Main client class that receives and displays screen streams"""
    
    def __init__(self, server_host: str, server_port: int = 5050):
        self.server_host = server_host
        self.server_port = server_port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.connected = False
        
        # Frame data
        self.width = 640
        self.height = 480
        self.current_frame: Optional[bytes] = None
        self.frame_lock = threading.Lock()
        
        # Statistics
        self.frames_received = 0
        self.bytes_received = 0
        self.last_fps_time = time.time()
        self.fps = 0.0
        self.latency_sum = 0
        self.latency_count = 0
    
    def connect(self) -> bool:
        """Connect to the server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.server_host, self.server_port))
            self.socket.settimeout(None)
            
            print(f"[+] Connected to {self.server_host}:{self.server_port}")
            
            # Send hello message
            self._send_message(MessageType.HELLO, b'')
            
            self.connected = True
            return True
            
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from server"""
        if self.socket:
            try:
                self._send_message(MessageType.DISCONNECT, b'')
                self.socket.close()
            except:
                pass
        self.connected = False
        print("[-] Disconnected")
    
    def _send_message(self, msg_type: MessageType, data: bytes):
        """Send a message to the server"""
        if self.socket:
            header = MessageHeader(msg_type=msg_type, flags=0, 
                                  sequence=0, size=len(data))
            self.socket.sendall(header.pack() + data)
    
    def receive_loop(self):
        """Main receiving loop"""
        while self.running and self.connected:
            try:
                # Receive header
                header_data = self.socket.recv(HEADER_SIZE)
                if len(header_data) < HEADER_SIZE:
                    continue
                
                header = MessageHeader.unpack(header_data)
                
                # Receive payload
                payload = b''
                remaining = header.size
                while remaining > 0:
                    chunk = self.socket.recv(min(BUFFER_SIZE, remaining))
                    if not chunk:
                        break
                    payload += chunk
                    remaining -= len(chunk)
                
                # Process message
                self._process_message(header, payload)
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[-] Receive error: {e}")
                self.connected = False
                break
    
    def _process_message(self, header: MessageHeader, payload: bytes):
        """Process incoming message"""
        if header.msg_type == MessageType.HELLO_ACK:
            print("[+] Server acknowledged connection")
            
        elif header.msg_type == MessageType.SCREEN_DATA:
            if header.flags == 1:
                # Resolution info
                if len(payload) >= 8:
                    self.width, self.height = struct.unpack("!II", payload[:8])
                    print(f"Resolution: {self.width}x{self.height}")
            else:
                # Frame data
                self._process_frame(payload)
                
        elif header.msg_type == MessageType.HEARTBEAT:
            pass  # Keep-alive received
    
    def _process_frame(self, payload: bytes):
        """Process received frame data"""
        if len(payload) < 16:
            return
        
        # Extract metadata
        sequence, timestamp, checksum = struct.unpack("!IIQ", payload[:16])
        compressed_data = payload[16:]
        
        try:
            # Decompress frame
            frame_data = decompress_data(compressed_data)
            
            # Verify checksum
            if sum(frame_data) & 0xFFFFFFFF != checksum:
                print("[!] Checksum mismatch")
                return
            
            # Update frame
            with self.frame_lock:
                self.current_frame = frame_data
            
            # Update statistics
            self.frames_received += 1
            self.bytes_received += len(payload)
            
            # Calculate FPS
            current_time = time.time()
            if current_time - self.last_fps_time >= 1.0:
                self.fps = self.frames_received / (current_time - self.last_fps_time)
                self.frames_received = 0
                self.last_fps_time = current_time
            
            # Calculate latency
            latency = current_time - (timestamp / 1000.0)
            self.latency_sum += latency
            self.latency_count += 1
            
        except Exception as e:
            print(f"Frame processing error: {e}")
    
    def get_current_frame(self) -> Optional[bytes]:
        """Get the current frame safely"""
        with self.frame_lock:
            return self.current_frame
    
    def get_stats(self) -> dict:
        """Get connection statistics"""
        avg_latency = self.latency_sum / max(1, self.latency_count)
        return {
            'fps': self.fps,
            'bytes': self.bytes_received,
            'latency_ms': avg_latency * 1000,
            'resolution': f"{self.width}x{self.height}"
        }


class ViewerWindow:
    """GUI window for displaying the screen stream"""
    
    def __init__(self, client: ScreenViewerClient):
        self.client = client
        self.root = tk.Tk()
        self.root.title("ScreenViewer Client")
        
        # Create canvas for video display
        self.canvas = tk.Canvas(self.root, width=client.width, height=client.height)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Connecting...")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, 
                                   relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Control buttons
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(fill=tk.X, side=tk.TOP)
        
        self.disconnect_btn = tk.Button(self.button_frame, text="Disconnect", 
                                        command=self._on_disconnect)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.fullscreen_btn = tk.Button(self.button_frame, text="Fullscreen", 
                                        command=self._toggle_fullscreen)
        self.fullscreen_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.is_fullscreen = False
        self.photo_image = None
        
        # Start update loop
        self.update_display()
    
    def _on_disconnect(self):
        """Handle disconnect button click"""
        self.client.running = False
        self.client.disconnect()
        self.root.quit()
    
    def _toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes('-fullscreen', self.is_fullscreen)
    
    def update_display(self):
        """Update the display with new frames"""
        if self.client.running:
            frame = self.client.get_current_frame()
            
            if frame:
                try:
                    # Convert raw RGB data to image
                    img = Image.frombytes("RGB", (self.client.width, self.client.height), 
                                         frame, "raw", "RGB")
                    
                    # Resize to fit window if needed
                    canvas_width = self.canvas.winfo_width()
                    canvas_height = self.canvas.winfo_height()
                    
                    if canvas_width > 1 and canvas_height > 1:
                        img = img.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS)
                    
                    self.photo_image = ImageTk.PhotoImage(img)
                    
                    # Display image
                    self.canvas.delete("all")
                    self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)
                    
                    # Update status
                    stats = self.client.get_stats()
                    self.status_var.set(
                        f"FPS: {stats['fps']:.1f} | "
                        f"Latency: {stats['latency_ms']:.1f}ms | "
                        f"Resolution: {stats['resolution']} | "
                        f"Data: {stats['bytes']/1024:.1f}KB"
                    )
                    
                except Exception as e:
                    self.status_var.set(f"Error: {e}")
        
        # Schedule next update
        self.root.after(33, self.update_display)  # ~30 FPS
    
    def run(self):
        """Start the GUI event loop"""
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='ScreenViewer Client')
    parser.add_argument('host', help='Server host IP address')
    parser.add_argument('--port', type=int, default=5050, help='Server port')
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI (stats only)')
    
    args = parser.parse_args()
    
    if not TK_AVAILABLE and not args.no_gui:
        print("Error: tkinter not available. Install with: pip install pillow")
        print("Or use --no-gui flag for stats-only mode")
        sys.exit(1)
    
    # Create and connect client
    client = ScreenViewerClient(args.host, args.port)
    
    if not client.connect():
        sys.exit(1)
    
    # Start receive thread
    client.running = True
    receive_thread = threading.Thread(target=client.receive_loop, daemon=True)
    receive_thread.start()
    
    print("\nScreenViewer Client Started")
    print("=" * 40)
    
    if args.no_gui:
        # Stats-only mode
        try:
            while client.running and client.connected:
                time.sleep(1)
                stats = client.get_stats()
                print(f"FPS: {stats['fps']:.1f} | "
                      f"Latency: {stats['latency_ms']:.1f}ms | "
                      f"Data: {stats['bytes']/1024:.1f}KB")
        except KeyboardInterrupt:
            pass
    else:
        # GUI mode
        viewer = ViewerWindow(client)
        viewer.run()
    
    client.disconnect()
    print("Client stopped")


if __name__ == '__main__':
    main()
