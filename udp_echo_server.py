#!/usr/bin/env python3
"""
UDP Echo Server with microsecond timing for Raspberry Pi 3B+ (Debian 13)
Echoes back received packets with timestamps for latency measurement
"""

import socket
import time
import sys
import argparse
import csv
from datetime import datetime

# Configuration
SERVER_IP = "0.0.0.0"  # Listen on all interfaces
SERVER_PORT = 5005
BUFFER_SIZE = 65535

def main():
    parser = argparse.ArgumentParser(description='UDP Echo Server with microsecond timing')
    parser.add_argument('-p', '--port', type=int, default=SERVER_PORT,
                        help=f'Server port (default: {SERVER_PORT})')
    parser.add_argument('--log', type=str, default=None,
                        help='Path to CSV log file (default: auto-generated)')
    args = parser.parse_args()

    log_path = args.log
    if not log_path:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = f"udp_echo_server_{ts}.csv"

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Bind to address
    try:
        sock.bind((SERVER_IP, args.port))
        print(f"UDP Echo Server listening on {SERVER_IP}:{args.port}")
        print(f"Waiting for packets... (Press Ctrl+C to exit)")
        print(f"Log file: {log_path}")
    except OSError as e:
        print(f"Error binding to {SERVER_IP}:{args.port}: {e}")
        sys.exit(1)
    
    packet_count = 0
    log_file = open(log_path, 'w', newline='')
    log_writer = csv.writer(log_file)
    log_writer.writerow([
        'packet',
        'recv_time_epoch',
        'send_time_epoch',
        'recv_time_iso',
        'send_time_iso',
        'processing_time_us',
        'packet_size_bytes',
        'from_ip',
        'from_port'
    ])
    log_file.flush()
    
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

            log_writer.writerow([
                packet_count,
                f"{recv_time:.9f}",
                f"{send_time:.9f}",
                datetime.fromtimestamp(recv_time).isoformat(),
                datetime.fromtimestamp(send_time).isoformat(),
                f"{processing_time_us:.2f}",
                len(data),
                client_addr[0],
                client_addr[1]
            ])
            log_file.flush()
            
    except KeyboardInterrupt:
        print(f"\n\nServer shutting down...")
        print(f"Total packets processed: {packet_count}")
    finally:
        sock.close()
        log_file.close()

if __name__ == "__main__":
    main()
