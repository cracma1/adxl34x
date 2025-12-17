import spidev
READ = 0x80; MB = 0x40
 
def whoami(bus, dev):
    s = spidev.SpiDev(); s.open(bus, dev)
    s.mode = 0b11            # ADXL345 requires SPI mode 3
    s.max_speed_hz = 5_000_000
    resp = s.xfer2([READ | 0x00, 0x00])   # DEVID @ 0x00
    s.close()
    return resp[1]
 
print("CE0 (/dev/spidev0.0):", hex(whoami(0,0)))
print
