#!/usr/bin/env python3
"""
UDP Echo Client with microsecond timing for Debian 13 Linux laptop
Sends packets to server and measures round-trip time (RTT)
"""

import socket
import time
import struct
import statistics
import sys
import argparse

# Default configuration
DEFAULT_SERVER_IP = "192.168.1.100"  # Change to your Raspberry Pi IP
DEFAULT_SERVER_PORT = 5005
DEFAULT_PACKET_SIZE = 64
DEFAULT_COUNT = 100
DEFAULT_INTERVAL = 0.01  # 10ms between packets

class UDPEchoClient:
    def __init__(self, server_ip, server_port, packet_size=64):
        self.server_ip = server_ip
        self.server_port = server_port
        self.packet_size = packet_size
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set socket timeout to 2 seconds
        self.sock.settimeout(2.0)
        
        self.rtts = []  # Store round-trip times in microseconds
        self.sent_count = 0
        self.received_count = 0
        
    def send_packet(self, sequence):
        """Send a packet and measure RTT"""
        # Create payload with sequence number and timestamp
        timestamp = time.time()
        payload = struct.pack('!Id', sequence, timestamp)
        # Pad to desired packet size
        payload += b'x' * (self.packet_size - len(payload))
        
        try:
            # Send packet
            send_time = time.time()
            self.sock.sendto(payload, (self.server_ip, self.server_port))
            self.sent_count += 1
            
            # Receive echo
            data, addr = self.sock.recvfrom(65535)
            recv_time = time.time()
            self.received_count += 1
            
            # Calculate RTT in microseconds
            rtt_us = (recv_time - send_time) * 1_000_000
            self.rtts.append(rtt_us)
            
            # Unpack sequence number
            recv_seq, recv_ts = struct.unpack('!Id', data[:12])
            
            print(f"[{sequence:06d}] RTT: {rtt_us:8.2f} µs | "
                  f"Size: {len(data):5d} bytes | "
                  f"From: {addr[0]}:{addr[1]}")
            
            return rtt_us
            
        except socket.timeout:
            print(f"[{sequence:06d}] Timeout - no response from server")
            return None
        except Exception as e:
            print(f"[{sequence:06d}] Error: {e}")
            return None
    
    def run(self, count=100, interval=0.01):
        """Run the echo test"""
        print(f"UDP Echo Client")
        print(f"Target: {self.server_ip}:{self.server_port}")
        print(f"Packet size: {self.packet_size} bytes")
        print(f"Count: {count} packets")
        print(f"Interval: {interval*1000:.1f} ms")
        print("-" * 70)
        
        try:
            for seq in range(1, count + 1):
                self.send_packet(seq)
                
                # Wait before sending next packet (except for last one)
                if seq < count:
                    time.sleep(interval)
                    
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
        finally:
            self.print_statistics()
            self.sock.close()
    
    def print_statistics(self):
        """Print summary statistics"""
        print("\n" + "=" * 70)
        print("STATISTICS")
        print("=" * 70)
        print(f"Packets sent:     {self.sent_count}")
        print(f"Packets received: {self.received_count}")
        
        if self.sent_count > 0:
            loss_rate = ((self.sent_count - self.received_count) / self.sent_count) * 100
            print(f"Packet loss:      {loss_rate:.2f}%")
        
        if self.rtts:
            print(f"\nRound-Trip Time (RTT) in microseconds:")
            print(f"  Minimum:   {min(self.rtts):10.2f} µs")
            print(f"  Maximum:   {max(self.rtts):10.2f} µs")
            print(f"  Mean:      {statistics.mean(self.rtts):10.2f} µs")
            print(f"  Median:    {statistics.median(self.rtts):10.2f} µs")
            
            if len(self.rtts) > 1:
                print(f"  Std Dev:   {statistics.stdev(self.rtts):10.2f} µs")
            
            # Calculate percentiles
            sorted_rtts = sorted(self.rtts)
            p50 = sorted_rtts[int(len(sorted_rtts) * 0.50)]
            p95 = sorted_rtts[int(len(sorted_rtts) * 0.95)]
            p99 = sorted_rtts[int(len(sorted_rtts) * 0.99)]
            
            print(f"\n  50th percentile: {p50:10.2f} µs")
            print(f"  95th percentile: {p95:10.2f} µs")
            print(f"  99th percentile: {p99:10.2f} µs")
        else:
            print("\nNo successful round-trips recorded")

def main():
    parser = argparse.ArgumentParser(description='UDP Echo Client with microsecond timing')
    parser.add_argument('-s', '--server', type=str, default=DEFAULT_SERVER_IP,
                        help=f'Server IP address (default: {DEFAULT_SERVER_IP})')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_SERVER_PORT,
                        help=f'Server port (default: {DEFAULT_SERVER_PORT})')
    parser.add_argument('-c', '--count', type=int, default=DEFAULT_COUNT,
                        help=f'Number of packets to send (default: {DEFAULT_COUNT})')
    parser.add_argument('-z', '--size', type=int, default=DEFAULT_PACKET_SIZE,
                        help=f'Packet size in bytes (default: {DEFAULT_PACKET_SIZE})')
    parser.add_argument('-i', '--interval', type=float, default=DEFAULT_INTERVAL,
                        help=f'Interval between packets in seconds (default: {DEFAULT_INTERVAL})')
    
    args = parser.parse_args()
    
    # Validate packet size
    if args.size < 12:
        print("Error: Packet size must be at least 12 bytes")
        sys.exit(1)
    
    # Create and run client
    client = UDPEchoClient(args.server, args.port, args.size)
    client.run(args.count, args.interval)

if __name__ == "__main__":
    main()
