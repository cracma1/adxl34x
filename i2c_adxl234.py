#!/usr/bin/env python3
# Raspberry Pi 3B+ + ADXL345 over I2C (minimal imports)
import time
from smbus import SMBus
 
# Registers (per ADXL345 datasheet)
REG_DEVID       = 0x00  # WHOAMI = 0xE5
REG_BW_RATE     = 0x2C  # Output data rate
REG_POWER_CTL   = 0x2D  # Measure bit
REG_DATA_FORMAT = 0x31  # Full-res, range
REG_DATAX0      = 0x32  # X0..Z1 (6 bytes)
 
ADDR_DEFAULT = 0x53     # SDO=GND
ADDR_ALT     = 0x1D     # SDO=VDD
 
# Full-res scale factor (typical): ~3.9 mg/LSB -> m/s^2 per LSB
SCALE_M_S2_PER_LSB = 0.0039 * 9.806  # ~0.0383 m/s^2 per LSB
 
def to_int16_le(lo, hi):
    val = lo | (hi << 8)
    return val - 0x10000 if val & 0x8000 else val
 
def detect_address(bus):
    for addr in (ADDR_DEFAULT, ADDR_ALT):
        try:
            if bus.read_byte_data(addr, REG_DEVID) == 0xE5:
                return addr
        except OSError:
            pass
    raise RuntimeError("ADXL345 not found at 0x53 or 0x1D; check wiring/SDA/SCL.")
 
def init_adxl(bus, addr):
    # Put in standby, configure, then start measurement (datasheet recommendation)
    bus.write_byte_data(addr, REG_POWER_CTL, 0x00)      # standby
    bus.write_byte_data(addr, REG_BW_RATE,     0x0A)    # 100 Hz
    bus.write_byte_data(addr, REG_DATA_FORMAT, 0x08)    # FULL_RES=1, ±2g, right-justified
    bus.write_byte_data(addr, REG_POWER_CTL,   0x08)    # Measure=1
 
def read_accel(bus, addr):
    data = bus.read_i2c_block_data(addr, REG_DATAX0, 6)
    x = to_int16_le(data[0], data[1]) * SCALE_M_S2_PER_LSB
    y = to_int16_le(data[2], data[3]) * SCALE_M_S2_PER_LSB
    z = to_int16_le(data[4], data[5]) * SCALE_M_S2_PER_LSB
    return x, y, z
 
def main():
    bus = SMBus(1)  # I2C bus 1 on Pi
    addr = detect_address(bus)
    init_adxl(bus, addr)
    print(f"ADXL345 at 0x{addr:02X} initialized (I2C, full-res, 100 Hz).")
    try:
               while True:
            ax, ay, az = read_accel(bus, addr)
            print(f"X={ax:+.3f} m/s^2  Y={ay:+.3f} m/s^2  Z={az:+.3f} m/s^2")
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        bus.close()
 
if __name__ == "__main__":
    main()
 
