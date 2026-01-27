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
import csv
from datetime import datetime

# Default configuration
DEFAULT_SERVER_IP = "192.168.1.100"  # Change to your Raspberry Pi IP
DEFAULT_SERVER_PORT = 5005
DEFAULT_PACKET_SIZE = 64
DEFAULT_COUNT = 100
DEFAULT_INTERVAL = 0.01  # 10ms between packets

class UDPEchoClient:
    def __init__(self, server_ip, server_port, packet_size=64, log_path=None):
        self.server_ip = server_ip
        self.server_port = server_port
        self.packet_size = packet_size
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set socket timeout to 2 seconds
        self.sock.settimeout(2.0)
        
        self.rtts = []  # Store round-trip times in microseconds
        self.sent_count = 0
        self.received_count = 0

        self.log_path = log_path
        self.log_file = None
        self.log_writer = None

    def _init_log(self):
        if not self.log_path:
            return
        self.log_file = open(self.log_path, 'w', newline='')
        self.log_writer = csv.writer(self.log_file)
        self.log_writer.writerow([
            'sequence',
            'status',
            'send_time_epoch',
            'recv_time_epoch',
            'send_time_iso',
            'recv_time_iso',
            'rtt_us',
            'packet_size_bytes',
            'from_ip',
            'from_port',
            'error'
        ])
        self.log_file.flush()

    def _close_log(self):
        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.log_writer = None

    def _log_statistics(self):
        if not self.log_writer:
            return
        loss_rate = None
        if self.sent_count > 0:
            loss_rate = ((self.sent_count - self.received_count) / self.sent_count) * 100

        stats_row = {
            'sent': self.sent_count,
            'received': self.received_count,
            'loss_rate_percent': f"{loss_rate:.2f}" if loss_rate is not None else ''
        }

        self.log_writer.writerow([])
        self.log_writer.writerow(["STATISTICS"])
        self.log_writer.writerow(["=" * 70])
        self.log_writer.writerow([f"Packets sent:     {self.sent_count}"])
        self.log_writer.writerow([f"Packets received: {self.received_count}"])
        if loss_rate is not None:
            self.log_writer.writerow([f"Packet loss:      {loss_rate:.2f}%"])

        if self.rtts:
            self.log_writer.writerow([""])
            self.log_writer.writerow(["Round-Trip Time (RTT) in microseconds:"])
            self.log_writer.writerow([f"  Minimum:   {min(self.rtts):10.2f} µs"])
            self.log_writer.writerow([f"  Maximum:   {max(self.rtts):10.2f} µs"])
            self.log_writer.writerow([f"  Mean:      {statistics.mean(self.rtts):10.2f} µs"])
            self.log_writer.writerow([f"  Median:    {statistics.median(self.rtts):10.2f} µs"])

            if len(self.rtts) > 1:
                self.log_writer.writerow([f"  Std Dev:   {statistics.stdev(self.rtts):10.2f} µs"])

            sorted_rtts = sorted(self.rtts)
            p50 = sorted_rtts[int(len(sorted_rtts) * 0.50)]
            p95 = sorted_rtts[int(len(sorted_rtts) * 0.95)]
            p99 = sorted_rtts[int(len(sorted_rtts) * 0.99)]

            self.log_writer.writerow([""])
            self.log_writer.writerow([f"  50th percentile: {p50:10.2f} µs"])
            self.log_writer.writerow([f"  95th percentile: {p95:10.2f} µs"])
            self.log_writer.writerow([f"  99th percentile: {p99:10.2f} µs"])
        else:
            self.log_writer.writerow([""])
            self.log_writer.writerow(["No successful round-trips recorded"])

        self.log_file.flush()

    def _log_row(self, sequence, status, send_time=None, recv_time=None,
                 rtt_us=None, packet_size=None, addr=None, error=None):
        if not self.log_writer:
            return
        send_iso = datetime.fromtimestamp(send_time).isoformat() if send_time else ''
        recv_iso = datetime.fromtimestamp(recv_time).isoformat() if recv_time else ''
        from_ip = addr[0] if addr else ''
        from_port = addr[1] if addr else ''
        self.log_writer.writerow([
            sequence,
            status,
            f"{send_time:.9f}" if send_time else '',
            f"{recv_time:.9f}" if recv_time else '',
            send_iso,
            recv_iso,
            f"{rtt_us:.2f}" if rtt_us is not None else '',
            packet_size if packet_size is not None else '',
            from_ip,
            from_port,
            error or ''
        ])
        self.log_file.flush()
        
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

            self._log_row(
                sequence=sequence,
                status='ok',
                send_time=send_time,
                recv_time=recv_time,
                rtt_us=rtt_us,
                packet_size=len(data),
                addr=addr
            )
            
            return rtt_us
            
        except socket.timeout:
            print(f"[{sequence:06d}] Timeout - no response from server")
            self._log_row(sequence=sequence, status='timeout', error='timeout')
            return None
        except Exception as e:
            print(f"[{sequence:06d}] Error: {e}")
            self._log_row(sequence=sequence, status='error', error=str(e))
            return None
    
    def run(self, count=100, interval=0.01):
        """Run the echo test"""
        print(f"UDP Echo Client")
        print(f"Target: {self.server_ip}:{self.server_port}")
        print(f"Packet size: {self.packet_size} bytes")
        print(f"Count: {count} packets")
        print(f"Interval: {interval*1000:.1f} ms")
        if self.log_path:
            print(f"Log file: {self.log_path}")
        print("-" * 70)

        self._init_log()
        
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
            self._log_statistics()
            self._close_log()
    
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
    parser.add_argument('--log', type=str, default=None,
                        help='Path to CSV log file (default: auto-generated)')
    
    args = parser.parse_args()
    
    # Validate packet size
    if args.size < 12:
        print("Error: Packet size must be at least 12 bytes")
        sys.exit(1)

    log_path = args.log
    if not log_path:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = f"udp_echo_client_{ts}.csv"
    
    # Create and run client
    client = UDPEchoClient(args.server, args.port, args.size, log_path=log_path)
    client.run(args.count, args.interval)

if __name__ == "__main__":
    main()
