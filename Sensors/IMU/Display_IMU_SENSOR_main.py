
import time
import math
import board
import busio
import adafruit_mpu6050
import adafruit_ssd1306

# I2C SETUP
# OLED: GP18 SDA, GP19 SCL
oled_i2c = busio.I2C(
    scl=board.GP19,
    sda=board.GP18,
    frequency=400000
)
display = adafruit_ssd1306.SSD1306_I2C(
    128, 64, oled_i2c, addr=0x3C
)
# IMU: GP16 SDA, GP17 SCL
# again they can techinally share the I2C pins but i dont have room on my female pin headers for 2 wires so seperated now.
imu_i2c = busio.I2C(
    scl=board.GP17,
    sda=board.GP16,
    frequency=400000
)

imu = adafruit_mpu6050.MPU6050(imu_i2c)

# 3D CUBE TIME
# Cube vertices
vertices = [
    (-1, -1, -1),
    ( 1, -1, -1),
    ( 1,  1, -1),
    (-1,  1, -1),
    (-1, -1,  1),
    ( 1, -1,  1),
    ( 1,  1,  1),
    (-1,  1,  1)
]

# Cube edges
edges = [
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7)
]


def rotate_vertex(vertex, roll, pitch):
    x, y, z = vertex

    # Rotate around X (roll)
    y1 = y * math.cos(roll) - z * math.sin(roll)
    z1 = y * math.sin(roll) + z * math.cos(roll)

    # Rotate around Y (pitch)
    x2 = x * math.cos(pitch) + z1 * math.sin(pitch)
    z2 = -x * math.sin(pitch) + z1 * math.cos(pitch)

    return x2, y1, z2


def project_vertex(vertex):
    x, y, z = vertex

    scale = 15
    distance = 4

    factor = distance / (distance + z)

    screen_x = int(91 + x * scale * factor)
    screen_y = int(31 + y * scale * factor)

    return screen_x, screen_y


def draw_cube(roll, pitch):
    points = []

    for vertex in vertices:
        rotated = rotate_vertex(vertex, roll, pitch)
        projected = project_vertex(rotated)
        points.append(projected)

    # Draw cube edges
    for edge in edges:
        p1 = points[edge[0]]
        p2 = points[edge[1]]

        display.line(
            p1[0], p1[1],
            p2[0], p2[1],
            1
        )

print("MPU6050 initialized")
print("3D orientation display active")

while True:
    try:
        # Read accelerometer
        ax, ay, az = imu.acceleration

        # Calculate orientation
        roll = math.atan2(ay, az)

        pitch = math.atan2(
            -ax,
            math.sqrt(ay * ay + az * az)
        )

        roll_deg = math.degrees(roll)
        pitch_deg = math.degrees(pitch)

        # Draw OLED
        display.fill(0)

        display.text("IMU ORIENTATION", 0, 0, 1)
        display.hline(0, 10, 128, 1)

        # Orientation values
        display.text(
            "R:{:+.0f}".format(roll_deg),
            0, 17, 1
        )

        display.text(
            "P:{:+.0f}".format(pitch_deg),
            0, 29, 1
        )

        # Draw rotating cube
        draw_cube(roll, pitch)

        display.show()

        time.sleep(0.05)

    except Exception as error:
        print("IMU ERROR:", error)
        time.sleep(1)
