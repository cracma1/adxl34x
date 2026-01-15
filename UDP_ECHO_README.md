# UDP Echo Server/Client with Microsecond Timing

High-precision UDP echo server and client for latency measurement between Raspberry Pi 3B+ and Linux laptop over direct LAN connection.

## Files

- **udp_echo_server.py** - Server for Raspberry Pi 3B+ (Debian 13)
- **udp_echo_client.py** - Client for Debian 13 Linux laptop

## Features

- **Microsecond precision timing** using `time.time()`
- **Low-latency echo** - immediate packet reflection
- **Comprehensive statistics** - min/max/mean/median/percentiles
- **Packet loss tracking**
- **Configurable packet sizes** and test parameters
- **Real-time monitoring** of RTT for each packet

## Setup

### On Raspberry Pi 3B+ (Server)

1. Copy `udp_echo_server.py` to your Raspberry Pi
2. Make it executable:
   ```bash
   chmod +x udp_echo_server.py
   ```

3. Find your Pi's IP address:
   ```bash
   ip addr show
   ```

4. Run the server:
   ```bash
   python3 udp_echo_server.py
   ```
   Or:
   ```bash
   ./udp_echo_server.py
   ```

### On Linux Laptop (Client)

1. Copy `udp_echo_client.py` to your laptop
2. Make it executable:
   ```bash
   chmod +x udp_echo_client.py
   ```

3. Run the client (replace IP with your Pi's IP):
   ```bash
   python3 udp_echo_client.py -s 192.168.1.100
   ```
   Or:
   ```bash
   ./udp_echo_client.py -s 192.168.1.100
   ```

## Usage Examples

### Basic Test (100 packets, 64 bytes each)
```bash
python3 udp_echo_client.py -s 192.168.1.100
```

### Custom Packet Count
```bash
python3 udp_echo_client.py -s 192.168.1.100 -c 1000
```

### Custom Packet Size (1KB)
```bash
python3 udp_echo_client.py -s 192.168.1.100 -z 1024
```

### High-Frequency Test (1ms interval, 1000 packets)
```bash
python3 udp_echo_client.py -s 192.168.1.100 -c 1000 -i 0.001
```

### Large Packet Test
```bash
python3 udp_echo_client.py -s 192.168.1.100 -z 8192 -c 500
```

## Command-Line Options

### Client Options

```
-s, --server    Server IP address (default: 192.168.1.100)
-p, --port      Server port (default: 5005)
-c, --count     Number of packets to send (default: 100)
-z, --size      Packet size in bytes (default: 64)
-i, --interval  Interval between packets in seconds (default: 0.01)
```

### Help
```bash
python3 udp_echo_client.py --help
```

## Network Configuration

### Direct LAN Connection

For optimal performance with direct LAN connection between Pi and laptop:

1. **Static IP Configuration** (recommended)

   On Raspberry Pi, edit `/etc/network/interfaces` or use `nmcli`:
   ```bash
   sudo nmcli con mod "Wired connection 1" ipv4.addresses 192.168.100.1/24
   sudo nmcli con mod "Wired connection 1" ipv4.method manual
   sudo nmcli con up "Wired connection 1"
   ```

   On laptop:
   ```bash
   sudo nmcli con mod "Wired connection 1" ipv4.addresses 192.168.100.2/24
   sudo nmcli con mod "Wired connection 1" ipv4.method manual
   sudo nmcli con up "Wired connection 1"
   ```

2. **Test Connectivity**
   ```bash
   ping 192.168.100.1
   ```

### Firewall Configuration

If you have firewall enabled, allow UDP traffic on port 5005:

**On Raspberry Pi:**
```bash
sudo ufw allow 5005/udp
```

**On Laptop:**
```bash
sudo ufw allow out 5005/udp
```

## Output Example

### Server Output
```
UDP Echo Server listening on 0.0.0.0:5005
Waiting for packets... (Press Ctrl+C to exit)
[000001] From 192.168.100.2:54321 | Size:    64 bytes | Processing:   12.34 µs
[000002] From 192.168.100.2:54321 | Size:    64 bytes | Processing:   11.89 µs
[000003] From 192.168.100.2:54321 | Size:    64 bytes | Processing:   12.56 µs
```

### Client Output
```
UDP Echo Client
Target: 192.168.100.1:5005
Packet size: 64 bytes
Count: 100 packets
Interval: 10.0 ms
----------------------------------------------------------------------
[000001] RTT:   456.23 µs | Size:    64 bytes | From: 192.168.100.1:5005
[000002] RTT:   423.45 µs | Size:    64 bytes | From: 192.168.100.1:5005
[000003] RTT:   445.67 µs | Size:    64 bytes | From: 192.168.100.1:5005
...
======================================================================
STATISTICS
======================================================================
Packets sent:     100
Packets received: 100
Packet loss:      0.00%

Round-Trip Time (RTT) in microseconds:
  Minimum:      398.45 µs
  Maximum:      567.89 µs
  Mean:         445.23 µs
  Median:       442.18 µs
  Std Dev:       28.34 µs

  50th percentile:     442.18 µs
  95th percentile:     495.67 µs
  99th percentile:     523.45 µs
```

## Performance Tips

1. **Minimize System Load** - Close unnecessary applications on both systems
2. **Disable Power Management** - Disable CPU frequency scaling for consistent results:
   ```bash
   sudo cpupower frequency-set -g performance
   ```

3. **Use Real-Time Priority** (optional) - Run server with higher priority:
   ```bash
   sudo nice -n -20 python3 udp_echo_server.py
   ```

4. **Network Tuning** - Increase socket buffer sizes:
   ```bash
   sudo sysctl -w net.core.rmem_max=26214400
   sudo sysctl -w net.core.wmem_max=26214400
   ```

## Troubleshooting

### Connection Refused
- Verify server is running on Pi
- Check firewall settings
- Verify IP addresses are correct

### High Packet Loss
- Check network cable
- Verify no other network traffic
- Check system load on both machines

### Permission Denied on Port < 1024
- Use port 5005 or higher, or run with sudo

## Technical Details

- **Protocol**: UDP (connectionless)
- **Timing Method**: Python `time.time()` with microsecond precision
- **Default Port**: 5005
- **Buffer Size**: 65535 bytes (max UDP payload)
- **Timeout**: 2 seconds for client responses

## Requirements

- Python 3.7 or higher
- No external dependencies (uses only standard library)
- Direct LAN connection between devices
- Debian 13 (Trixie) on both systems

## License

Free to use and modify for testing and development purposes.
