"""
I needed somewhere to throw this right now,
this program should be ran on a laptop, not the dongle.
it listens over serial to the arduino or pi pico to dump the AMG8833 sensor output.
"""


import serial
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time

# CONFIGURATION

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200

ser = serial.Serial(
    SERIAL_PORT,
    BAUD_RATE,
    timeout=0
)

time.sleep(2)
ser.reset_input_buffer()

# THERMAL DATA

pixels = np.zeros((8, 8))
new_frame = False

frame_rows = []
packet_count = 0
last_frame_time = time.monotonic()

# FIGURE

plt.style.use("dark_background")

fig, ax = plt.subplots(figsize=(9, 8))

fig.canvas.manager.set_window_title("THERMAL CAMERA graphs")

image = ax.imshow(
    pixels,
    cmap="inferno",
    interpolation="bicubic",
    origin="upper",
    vmin=20,
    vmax=35
)

ax.set_title("AMG8833 THERMAL CAMERA", fontsize=16)
ax.set_xlabel("Sensor X")
ax.set_ylabel("Sensor Y")

colorbar = fig.colorbar(image, ax=ax)
colorbar.set_label("Temperature (°C)")

temperature_text = ax.text(
    0.02, -0.12,
    "",
    transform=ax.transAxes,
    fontsize=11
)

# SERIAL READER

def read_serial():

    global pixels
    global frame_rows
    global packet_count
    global last_frame_time

    while ser.in_waiting:

        try:
            line = ser.readline().decode(
                "utf-8",
                errors="ignore"
            ).strip()

        except Exception:
            continue

        if line == "FRAME":
            frame_rows = []
            continue

        # Ignore startup messages and separators
        if not line or "," not in line:
            continue

        try:
            values = [
                float(value)
                for value in line.split(",")
            ]

            if len(values) != 8:
                frame_rows = []
                continue

            frame_rows.append(values)

            if len(frame_rows) == 8:

                pixels = np.array(frame_rows)

                packet_count += 1
                last_frame_time = time.monotonic()

                frame_rows = []

        except ValueError:
            frame_rows = []


# DISPLAY UPDATE

def update(frame):

    read_serial()

    image.set_data(pixels)

    # Dynamic temperature range
    minimum = float(np.min(pixels))
    maximum = float(np.max(pixels))
    average = float(np.mean(pixels))

    # Keep a minimum color range of 2 degrees
    if maximum - minimum < 2:
        center = (maximum + minimum) / 2
        minimum = center - 1
        maximum = center + 1

    image.set_clim(minimum, maximum)

    elapsed = time.monotonic() - last_frame_time

    status = "CONNECTED" if elapsed < 2 else "WAITING FOR DATA"

    temperature_text.set_text(
        f"MIN: {minimum:.1f} °C    "
        f"MAX: {maximum:.1f} °C    "
        f"AVG: {average:.1f} °C    "
        f"FRAMES: {packet_count}    "
        f"STATUS: {status}"
    )

    return image, temperature_text


# RUN

ani = animation.FuncAnimation(
    fig,
    update,
    interval=50,
    blit=False,
    cache_frame_data=False
)

try:
    plt.tight_layout()
    plt.show()

finally:
    ser.close()
