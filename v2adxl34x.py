#!/usr/bin/env python3
import spidev
import time
 
# ---------- Constants (from ADXL345 datasheet) ----------
BUS, DEV = 0, 0                     # SPI0.CE0 -> /dev/spidev0.0
REG_DEVID       = 0x00              # Should read 0xE5
REG_BW_RATE     = 0x2C              # Output data rate
REG_POWER_CTL   = 0x2D              # Measure bit
REG_DATA_FORMAT = 0x31              # Full-res, range, SPI/justify bits
REG_DATAX0      = 0x32              # X0..Z1 (6 bytes)
 
READ_FLAG = 0x80                    # bit7=1 -> read
MB_FLAG   = 0x40                    # bit6=1 -> multi-byte
 
# Full-resolution scale factor (typ) ~3.9 mg/LSB -> m/s^2 per LSB
SCALE_M_S2_PER_LSB = 0.0039 * 9.806 # ≈ 0.0383 m/s^2 per LSB (typ)
 
# ---------- Low-level SPI helpers ----------
def open_spi(bus=BUS, dev=DEV, speed_hz=5_000_000, mode=0b11):
    spi = spidev.SpiDev()
    spi.open(bus, dev)
    spi.max_speed_hz = speed_hz   # ≤ 5 MHz per datasheet
    spi.mode = mode               # CPOL=1, CPHA=1 (mode 3)
    return spi
 
def write_reg(spi, reg, value):
    # 4-wire write: first byte = reg (bit7=0), second byte = value
    spi.xfer2([reg & 0x3F, value & 0xFF])
 
def read_regs(spi, start_reg, length):
    # 4-wire read: first byte = READ|reg|MB(if length>1), then dummy bytes
    cmd = READ_FLAG | (start_reg & 0x3F)
    if length > 1:
        cmd |= MB_FLAG
    resp = spi.xfer2([cmd] + [0x00] * length)
    return resp[1:]  # drop the command echo
 
def to_int16_le(lo, hi):
    val = lo | (hi << 8)
    return val - 0x10000 if val & 0x8000 else val
 
# ---------- ADXL345 init & read ----------
def init_adxl345(spi):
    # Verify device ID (should be 0xE5)
    devid = read_regs(spi, REG_DEVID, 1)[0]
    if devid != 0xE5:
        raise RuntimeError(f"ADXL345 DEVID mismatch: 0x{devid:02X} (expected 0xE5)")
 
    # Set data rate to 100 Hz (BW_RATE = 0x0A)  [see datasheet table]
    write_reg(spi, REG_BW_RATE, 0x0A)
 
    # DATA_FORMAT:
    #  - FULL_RES (bit3)=1 for ~3.9 mg/LSB across ranges
    #  - Range bits (D1..D0)=00 -> ±2g
    #  - SPI bit (D6)=0 for 4-wire
    #  - Justify (D2)=0 (right-justified)
    write_reg(spi, REG_DATA_FORMAT, 0x08)
 
    # POWER_CTL: set Measure (bit3)=1 to start measurements
    write_reg(spi, REG_POWER_CTL, 0x08)
 
def read_accel_m_s2(spi):
    data = read_regs(spi, REG_DATAX0, 6)  # X0,X1,Y0,Y1,Z0,Z1
    x = to_int16_le(data[0], data[1])
    y = to_int16_le(data[2], data[3])
    z = to_int16_le(data[4], data[5])
    # Convert raw counts to m/s^2 using full-res scale factor (typical)
    return (x * SCALE_M_S2_PER_LSB,
            y * SCALE_M_S2_PER_LSB,
            z * SCALE_M_S2_PER_LSB)
 
def main():
    spi = open_spi()
    try:
        init_adxl345(spi)
        print("ADXL345 initialized (SPI mode 3, 100 Hz).")
        while True:
            ax, ay, az = read_accel_m_s2(spi)
            print(f"X={ax:+.3f} m/s^2  Y={ay:+.3f} m/s^2  Z={az:+.3f} m/s^2")
            time.sleep(0.1)
    finally:
        spi.close()
 
if __name__ == "__main__":
