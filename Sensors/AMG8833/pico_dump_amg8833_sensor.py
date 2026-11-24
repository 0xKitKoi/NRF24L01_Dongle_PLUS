"""
This dumps the thermal cam's readings to serial, for the python script to read and dump to a very nice thermal graph with colors.
"""

import time
import board
import busio
import adafruit_amg88xx

# I2C CONFIGURATION
i2c = busio.I2C(
    scl=board.GP19,
    sda=board.GP18,
    frequency=400000
)

# SENSOR
sensor = adafruit_amg88xx.AMG88XX(i2c)

# STREAM CONFIGURATION
FRAME_DELAY = 0.1  # 10 FPS target

print("AMG8833 INITIALIZED")
print("STREAMING THERMAL DATA")

while True:
    try:
        # Read the 8x8 thermal array
        pixels = sensor.pixels

        print("FRAME")

        for row in pixels:
            print(",".join("{:.2f}".format(temp) for temp in row))

        time.sleep(FRAME_DELAY)

    except Exception as error:
        print("SENSOR ERROR:", error)
        time.sleep(1)
