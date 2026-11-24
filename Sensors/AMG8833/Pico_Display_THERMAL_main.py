
import time
import board
import busio
import adafruit_amg88xx
import adafruit_ssd1306

# OLED I2C BUS
# GP18 = SDA
# GP19 = SCL
oled_i2c = busio.I2C(
    scl=board.GP19,
    sda=board.GP18,
    frequency=400000
)
display = adafruit_ssd1306.SSD1306_I2C(
    128, 64, oled_i2c, addr=0x3C
)

# AMG8833 I2C BUS
# GP16 = SDA
# the thermal sensor and the oled display can technically be on the same pins, addressed differently,
# but my GPIO header cant put 2 pins on one header port so womp womp.
# GP17 = SCL
sensor_i2c = busio.I2C(
    scl=board.GP17,
    sda=board.GP16,
    frequency=400000
)

sensor = adafruit_amg88xx.AMG88XX(sensor_i2c, addr=0x68)


# DISPLAY CONFIGURATION
GRID_X = 0
GRID_Y = 12
CELL_W = 8
CELL_H = 6
FRAME_DELAY = 0.1

# THERMAL DISPLAY

def temperature_to_brightness(temp, low, high):
    if high == low:
        return 1

    value = (temp - low) / (high - low)

    return max(0, min(1, value))


def draw_thermal_frame(pixels):

    # Flatten temperature array
    values = []

    for row in pixels:
        for temp in row:
            values.append(temp)

    minimum = min(values)
    maximum = max(values)
    average = sum(values) / len(values)

    # Dynamic temperature range
    low = minimum
    high = maximum

    display.fill(0)

    # Header
    display.text("THERMAL CAMERA", 0, 0, 1)

    # Draw 8x8 thermal grid
    for y in range(8):
        for x in range(8):

            temp = pixels[y][x]

            brightness = temperature_to_brightness(
                temp, low, high
            )

            # Convert brightness into monochrome patterns
            if brightness > 0.85:
                pattern = 3
            elif brightness > 0.65:
                pattern = 2
            elif brightness > 0.40:
                pattern = 1
            else:
                pattern = 0

            px = GRID_X + x * CELL_W
            py = GRID_Y + y * CELL_H

            if pattern == 3:
                display.fill_rect(px, py, CELL_W - 1, CELL_H - 1, 1)

            elif pattern == 2:
                display.rect(px, py, CELL_W - 1, CELL_H - 1, 1)

            elif pattern == 1:
                display.pixel(px + 3, py + 2, 1)

    # Temperature information
    display.text(
        "MAX:{:.1f}C".format(maximum),
        70, 16, 1
    )

    display.text(
        "MIN:{:.1f}C".format(minimum),
        70, 27, 1
    )

    display.text(
        "AVG:{:.1f}C".format(average),
        70, 38, 1
    )

    # Hottest pixel location
    hottest_index = values.index(maximum)

    hot_x = hottest_index % 8
    hot_y = hottest_index // 8

    display.text(
        "HOT: {},{}".format(hot_x, hot_y),
        70, 49, 1
    )

    display.show()


print("AMG8833 INITIALIZED")
print("OLED THERMAL CAMERA ACTIVE")

while True:
    try:
        pixels = sensor.pixels

        draw_thermal_frame(pixels)

        time.sleep(FRAME_DELAY)

    except Exception as error:
        print("SENSOR ERROR:", error)
        time.sleep(1)
