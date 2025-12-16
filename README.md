# adxl34x

sudo apt-get install python3-pip
pip3 install spidev
pip3 install adafruit-circuitpython-adxl34x


import busio
import digitalio
import board
import adafruit_adxl34x

# Create SPI bus
spi = busio.SPI(board.SCLK, board.MOSI, board.MISO)

# Chip select pin
cs = digitalio.DigitalInOut(board.D8)

# Initialize accelerometer
accelerometer = adafruit_adxl34x.ADXL345(spi, cs)

while True:
    x, y, z = accelerometer.acceleration
    print(f"X={x:.2f} m/s^2, Y={y:.2f} m/s^2, Z={z:.2f} m/s^2")
