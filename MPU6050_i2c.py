#!/usr/bin/env python3
# MPU-6050 I2C accelerometer reader for Raspberry Pi (minimal deps: python3-smbus)
import socket
PC_IP = "192.168.10.20" #<--replace with your ubuntu PC IP
PORT = 5005

import time, datetime
from smbus2 import SMBus
 
# Registers (MPU-6000/6050)
WHO_AM_I     = 0x75
PWR_MGMT_1   = 0x6B
SMPLRT_DIV   = 0x19
CONFIG       = 0x1A
ACCEL_CONFIG = 0x1C
ACCEL_XOUT_H = 0x3B  # XH, XL, YH, YL, ZH, ZL
 
LSB_PER_G = 16384.0     # +/-2g scale
G_TO_MS2  = 9.80665
 
def send_udp(text):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(text.encode(), (PC_IP, PORT))
    s.close()

def r8(bus, addr, reg):
    return bus.read_byte_data(addr, reg)
 
def w8(bus, addr, reg, val):
    bus.write_byte_data(addr, reg, val & 0xFF)
 
def rblk(bus, addr, reg, n):
    return bus.read_i2c_block_data(addr, reg, n)
 
def s16(msb, lsb):
    v = (msb << 8) | lsb
    return v - 65536 if (v & 0x8000) else v
 
def find_addr(bus):
    for a in (0x68, 0x69):  # AD0 low/high
        try:
            if r8(bus, a, WHO_AM_I) == 0x68:
                return a
        except OSError:
            pass
    raise RuntimeError("MPU-6050 not found at 0x68/0x69.")
 
def init_mpu(bus, addr):
    w8(bus, addr, PWR_MGMT_1, 0x00)  # wake
    time.sleep(0.05)
    w8(bus, addr, SMPLRT_DIV, 0x07)  # 1 kHz/(1+7)=125 Hz
    w8(bus, addr, CONFIG, 0x03)      # DLPF ~44 Hz
    w8(bus, addr, ACCEL_CONFIG, 0x00)  # +/-2g
 
def read_accel(bus, addr):
    b = rblk(bus, addr, ACCEL_XOUT_H, 6)
    ax = s16(b[0], b[1]) / LSB_PER_G * G_TO_MS2
    ay = s16(b[2], b[3]) / LSB_PER_G * G_TO_MS2
    az = s16(b[4], b[5]) / LSB_PER_G * G_TO_MS2
    return ax, ay, az
 
def main():
    bus = SMBus(1)  # /dev/i2c-1
    addr = find_addr(bus)
    init_mpu(bus, addr)
    print("MPU-6050 @ 0x%02X ready" % addr)
    try:
        while True:
            ax, ay, az = read_accel(bus, addr)
            ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
            # print("ts={} X=%+0.3f  Y=%+0.3f  Z=%+0.3f m/s^2".format(ts, ax, ay, az))
            line = "ts={} X={:.3f} Y={:.3f} Z={:.3f}".format(ts, ax, ay, az)
            time.sleep(0.5)
            print(line)
            send_udp(line)
    except KeyboardInterrupt:
        pass
    finally:
        bus.close()
 
if __name__ == "__main__":
    main()
    
