#!/usr/bin/env python3
"""
UDP Echo Server with microsecond timing for Raspberry Pi 3B+ (Debian 13)
Echoes back received packets with timestamps for latency measurement
"""

import socket
import time
import struct
import sys

# Configuration
SERVER_IP = "0.0.0.0"  # Listen on all interfaces
SERVER_PORT = 5005
BUFFER_SIZE = 65535

def main():
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Bind to address
    try:
        sock.bind((SERVER_IP, SERVER_PORT))
        print(f"UDP Echo Server listening on {SERVER_IP}:{SERVER_PORT}")
        print(f"Waiting for packets... (Press Ctrl+C to exit)")
    except OSError as e:
        print(f"Error binding to {SERVER_IP}:{SERVER_PORT}: {e}")
        sys.exit(1)
    
    packet_count = 0
    
    try:
        while True:
            # Receive data with microsecond timestamp
            data, client_addr = sock.recvfrom(BUFFER_SIZE)
            recv_time = time.time()  # Timestamp in seconds with microsecond precision
            
            packet_count += 1
            
            # Echo back the data immediately
            sock.sendto(data, client_addr)
            send_time = time.time()
            
            # Calculate processing time in microseconds
            processing_time_us = (send_time - recv_time) * 1_000_000
            
            # Display information
            print(f"[{packet_count:06d}] From {client_addr[0]}:{client_addr[1]} | "
                  f"Size: {len(data):5d} bytes | "
                  f"Processing: {processing_time_us:7.2f} µs")
            
    except KeyboardInterrupt:
        print(f"\n\nServer shutting down...")
        print(f"Total packets processed: {packet_count}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
