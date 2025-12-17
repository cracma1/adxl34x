#!/usr/bin/env python3
import time
from smbus import SMBus
 
# MPU-6050 registers
WHO_AM_I       = 0x75
PWR_MGMT_1     = 0x6B
SMPLRT_DIV     = 0x19
CONFIG         = 0x1A
ACCEL_CONFIG   = 0x1C
ACCEL_XOUT_H   = 0x3B  # XH, XL, YH, YL, ZH, ZL (6 bytes)
 
ADDRS = (0x68, 0x69)   # AD0=LOW/HIGH
 
# ±2g full-scale -> 16384 LSB/g
LSB_PER_G = 16384.0
G_TO_MS2  = 9.80665
 
def read_u8(bus, addr, reg):
    return bus.read_byte_data(addr, reg)
 
def write_u8(bus, addr, reg, val):
    bus.write_byte_data(addr, reg, val & 0xFF)
 
def read_block(bus, addr, reg, length):
    return bus.read_i2c_block_data(addr, reg, length)
 
def to_int16(msb, lsb):
    val = (msb << 8) | lsb
    return val - 0x10000 if val & 0x8000 else val
 
def detect_address(bus):
    for a in ADDRS:
        try:
            if read_u8(bus, a, WHO_AM_I) == 0x68:
                return a
        except OSError:
            pass
    raise RuntimeError("MPU-6050 not found at 0x68/0x69. Check wiring.")
 
def init_mpu(bus, addr):
    # Wake up
    write_u8(bus, addr, PWR_MGMT_1, 0x00)
    time.sleep(0.05)
 
    # Optional: sample rate & DLPF for cleaner accel output (1 kHz / (1+7) = 125 Hz)
    write_u8(bus, addr, SMPLRT_DIV, 0x07)  # 125 Hz
    write_u8(bus, addr, CONFIG, 0x03)      # DLPF=3 (~44 Hz bandwidth)
 
    # Accel ±2g (bits AFS_SEL=0)
    write_u8(bus, addr, ACCEL_CONFIG, 0x00)
 
def read_accel_ms2(bus, addr):
    b = read_block(bus, addr, ACCEL_XOUT_H, 6)
    ax = to_int16(b[0], b[1]) / LSB_PER_G * G_TO_MS2
    ay = to_int16(b[2], b[3]) / LSB_PER_G * G_TO_MS2
    az = to_int16(b[4], b[5]) / LSB_PER_G * G_TO_MS2
    return ax, ay, az
 
def main():
    bus = SMBus(1)  # I2C-1 on Raspberry Pi
    addr = detect_address(bus)
    init_mpu    init_mpu(bus, addr)
    print(f"MPU-6050 at 0x{addr:02X} ready (I²C, accel ±2g).")
    try:
        while True:
            ax, ay, az = read_accel_ms2(bus, addr)
            print(f"X={ax:+.3f} m/s²  Y={ay:+.3f} m/s²  Z={az:+.3f} m/s²")
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        bus.close()
 
if __name__ == "__main__":
    main()
