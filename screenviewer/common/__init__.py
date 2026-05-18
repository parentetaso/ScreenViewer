"""
ScreenViewer - Common utilities and constants
"""

import socket
import struct
import zlib
from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Optional

# Default configuration
DEFAULT_PORT = 5050
BUFFER_SIZE = 65536
COMPRESSION_LEVEL = 6

# Message types
class MessageType(Enum):
    HELLO = 1           # Client greeting
    HELLO_ACK = 2       # Server acknowledgment
    SCREEN_DATA = 3     # Screen frame data
    SCREEN_ACK = 4      # Frame acknowledgment
    DISCONNECT = 5      # Disconnect request
    HEARTBEAT = 6       # Keep-alive signal

# Message header format: type (1 byte) + flags (1 byte) + sequence (4 bytes) + size (4 bytes)
HEADER_FORMAT = "!BBII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

@dataclass
class MessageHeader:
    msg_type: MessageType
    flags: int
    sequence: int
    size: int
    
    def pack(self) -> bytes:
        return struct.pack(HEADER_FORMAT, self.msg_type.value, self.flags, self.sequence, self.size)
    
    @classmethod
    def unpack(cls, data: bytes) -> 'MessageHeader':
        msg_type, flags, sequence, size = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        return cls(
            msg_type=MessageType(msg_type),
            flags=flags,
            sequence=sequence,
            size=size
        )

def get_local_ip() -> str:
    """Get the local IP address of this machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def compress_data(data: bytes) -> bytes:
    """Compress data using zlib"""
    return zlib.compress(data, COMPRESSION_LEVEL)

def decompress_data(data: bytes) -> bytes:
    """Decompress data using zlib"""
    return zlib.decompress(data)

def calculate_checksum(data: bytes) -> int:
    """Calculate CRC32 checksum for data integrity"""
    return zlib.crc32(data) & 0xffffffff
