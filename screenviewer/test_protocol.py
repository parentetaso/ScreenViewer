#!/usr/bin/env python3
"""
Test script for ScreenViewer - Tests protocol and compression without GUI
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from common import (
    MessageType, MessageHeader, HEADER_SIZE,
    compress_data, decompress_data, get_local_ip, calculate_checksum
)
import struct
import time


def test_message_header():
    """Test message header packing/unpacking"""
    print("Testing Message Header...")
    
    header = MessageHeader(
        msg_type=MessageType.SCREEN_DATA,
        flags=1,
        sequence=12345,
        size=65536
    )
    
    packed = header.pack()
    assert len(packed) == HEADER_SIZE, f"Header size mismatch: {len(packed)} != {HEADER_SIZE}"
    
    unpacked = MessageHeader.unpack(packed)
    assert unpacked.msg_type == MessageType.SCREEN_DATA
    assert unpacked.flags == 1
    assert unpacked.sequence == 12345
    assert unpacked.size == 65536
    
    print("✓ Message header test passed")
    return True


def test_compression():
    """Test data compression/decompression"""
    print("\nTesting Compression...")
    
    # Create test data (simulating screen frame)
    width, height = 640, 480
    original_data = bytes([i % 256 for i in range(width * height * 3)])
    
    compressed = compress_data(original_data)
    decompressed = decompress_data(compressed)
    
    assert original_data == decompressed, "Decompression failed"
    
    compression_ratio = len(compressed) / len(original_data) * 100
    print(f"  Original size: {len(original_data)} bytes")
    print(f"  Compressed size: {len(compressed)} bytes")
    print(f"  Compression ratio: {compression_ratio:.1f}%")
    print("✓ Compression test passed")
    return True


def test_checksum():
    """Test checksum calculation"""
    print("\nTesting Checksum...")
    
    data = b"Hello, ScreenViewer!"
    checksum = calculate_checksum(data)
    
    assert checksum == calculate_checksum(data), "Checksum verification failed"
    
    wrong_data = b"Hello, ScreenViewer!!"
    assert checksum != calculate_checksum(wrong_data), "Checksum should differ for different data"
    
    print(f"  Checksum: {checksum}")
    print("✓ Checksum test passed")
    return True


def test_frame_simulation():
    """Simulate complete frame transmission"""
    print("\nTesting Frame Transmission Simulation...")
    
    # Create smaller frame data for testing
    width, height = 320, 240
    frame_data = bytes([int((i % 256)) for i in range(width * height * 3)])
    
    # Add metadata (use Q for timestamp to handle large values)
    sequence = 1
    timestamp = int(time.time() * 1000)
    checksum = sum(frame_data) & 0xFFFFFFFF
    
    metadata = struct.pack("!IQI", sequence, timestamp, checksum)
    
    # Compress
    compressed = compress_data(frame_data)
    payload = metadata + compressed
    
    # Create message header
    header = MessageHeader(
        msg_type=MessageType.SCREEN_DATA,
        flags=0,
        sequence=sequence,
        size=len(payload)
    )
    
    # Complete message
    message = header.pack() + payload
    
    # Simulate receiving
    received_header = MessageHeader.unpack(message[:HEADER_SIZE])
    received_payload = message[HEADER_SIZE:]
    
    # Extract metadata (use Q for timestamp to handle large values)
    recv_seq, recv_ts, recv_checksum = struct.unpack("!IQI", received_payload[:16])
    recv_compressed = received_payload[16:]
    
    # Decompress
    recv_frame = decompress_data(recv_compressed)
    
    # Verify
    assert recv_seq == sequence
    assert recv_checksum == checksum
    assert recv_frame == frame_data
    
    print(f"  Frame size: {len(frame_data)} bytes")
    print(f"  Message size: {len(message)} bytes")
    print(f"  Sequence: {sequence}")
    print(f"  Checksum verified: {recv_checksum == checksum}")
    print("✓ Frame transmission test passed")
    return True


def test_protocol_messages():
    """Test all protocol message types"""
    print("\nTesting Protocol Messages...")
    
    messages = [
        (MessageType.HELLO, b''),
        (MessageType.HELLO_ACK, b''),
        (MessageType.SCREEN_DATA, b'\x00\x01\x02\x03'),
        (MessageType.DISCONNECT, b''),
        (MessageType.HEARTBEAT, b''),
    ]
    
    for msg_type, data in messages:
        header = MessageHeader(msg_type=msg_type, flags=0, sequence=0, size=len(data))
        packed = header.pack() + data
        
        unpacked = MessageHeader.unpack(packed)
        assert unpacked.msg_type == msg_type
        print(f"  ✓ {msg_type.name} message OK")
    
    print("✓ All protocol messages test passed")
    return True


def main():
    print("=" * 60)
    print("ScreenViewer - Protocol Test Suite")
    print("=" * 60)
    print(f"\nLocal IP: {get_local_ip()}")
    print(f"Default Port: 5050")
    print(f"Header Size: {HEADER_SIZE} bytes\n")
    
    tests = [
        test_message_header,
        test_compression,
        test_checksum,
        test_frame_simulation,
        test_protocol_messages,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All tests passed! ScreenViewer protocol is working correctly.")
        print("\nTo use ScreenViewer:")
        print("  1. Start server: python server/server.py")
        print("  2. Connect client: python client/client.py <SERVER_IP>")
        return 0
    else:
        print("\n✗ Some tests failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())
