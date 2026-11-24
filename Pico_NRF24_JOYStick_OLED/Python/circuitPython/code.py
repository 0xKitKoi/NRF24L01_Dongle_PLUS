import board
import busio
import digitalio
import struct
import time
import math
import asyncio


import adafruit_ssd1306
from circuitpython_nrf24l01.rf24 import RF24

"""
JoyStick_Receiever_PICO-NRF24-DONGLE_main.py
Raspberry Pi Pico NRF24L01 dongle Main.py
JOYSTICK RECEIVER v1.1
This code listens over NRF24, and uses a small 128x64 OLED display to show the state of the transmitter.
The transmitter repo: 

Shows the Packet Count, and where the Joystick is.
The joystick transmitter is a battery powered pi pico with an nrf24, sending the state of a single joystick. simple pan and tilt capabilities.

"""


# OLED CONFIGURATION
# GP18 = SDA
# GP19 = SCL
i2c = busio.I2C(
    scl=board.GP19,
    sda=board.GP18,
    frequency=1_000_000 # [100_000, 400_000, 1_000_000, 3_400_000, 5_000_000]
)

# Scan for OLED
while not i2c.try_lock():
    pass

devices = i2c.scan()
i2c.unlock()

print("I2C devices:", [hex(d) for d in devices])

if 0x3C in devices:
    OLED_ADDRESS = 0x3C
elif 0x3D in devices:
    OLED_ADDRESS = 0x3D
else:
    raise RuntimeError("OLED not detected!")


display = adafruit_ssd1306.SSD1306_I2C(
    128,
    64,
    i2c,
    addr=OLED_ADDRESS
)

display.fill(0)
display.text("SCUZZY RADIO", 0, 10, 1)
display.text("INITIALIZING...", 0, 30, 1)
display.show()


# NRF24 CONFIGURATION
ADDRESS = b"1Node"
# The transmitter transmits to this address, we have to listen for it specifically.
"""
The nRF24 has six receive pipes, numbered 0 through 5.
radio.open_rx_pipe(0, ADDRESS)
radio.open_rx_pipe(1, ADDRESS)
radio.open_rx_pipe(2, ADDRESS)
Each pipe can listen for a different address. This allows one receiver to communicate with multiple transmitters without constantly changing its configuration.
"""

"""
We also have ack packets, that can be preloaded with a payload:
radio.ack = True
radio.dynamic_payloads = True
radio.ack_payloads = True
response = b"TEMP:24.5"
radio.load_ack(1, response)
# other device:
radio.send(b"GET_TEMP")

if radio.available():
    response = radio.read()
    print(response) # you can get the payload in the ack packet here.
    # half duplex, cant send and receive at same time.
"""


spi = busio.SPI(
    clock=board.GP2,
    MOSI=board.GP3,
    MISO=board.GP0
)


csn = digitalio.DigitalInOut(board.GP7)
csn.direction = digitalio.Direction.OUTPUT
csn.value = True

ce = digitalio.DigitalInOut(board.GP4)
ce.direction = digitalio.Direction.OUTPUT
ce.value = False

radio = RF24(
    spi,
    csn,
    ce,
    spi_frequency=1_000_000 # [500_000, 1_000_000, 2_000_000, 4_000_000, 5_000_000, 10_000_000]
)


# Channel: 0-125. 75 means 2475MHz. so 2400MHz to 2525Mhz. Each channel is spaced out 1MHz apart. 
radio.channel = 75
# over the air data rate, 250kbps has better receiver sensitivity and range. 1 is 1Mbps, good middle ground. 2 is 2Mbps, highest data rate but shorter range. 
radio.data_rate = 250
# output power. valid settings: [-18, -12, -6, 0] dBm. (dBm (decibel-milliwatts) is a logarithmic unit used to measure absolute power level relative to 1 milliwatt (mW))
# 0 is Maximum power output, maximum range as well. 
radio.pa_level = -12
# Packet's Cyclic Redundancy Check. A checksum is added to packets. 0 - disabled, 1- 8bit CRC, 2 - 16bit crc
radio.crc = 2
# address length. [3, 4, 5] bytes. b'1Node' is 5 bytes.
radio.address_length = 5

# Auto packet acks, acting as UDP right now. 
radio.auto_ack = False
# allows packets to have different lengths.
radio.dynamic_payloads = True

radio.open_rx_pipe(1, ADDRESS)
radio.listen = True

print("NRF24 receiver ready!")


# TELEMETRY VARIABLES

packet_count = 0

joystick_x = 0.0
joystick_y = 0.0
joystick_button = 1

last_packet_time = None

# Packet rate statistics
rate_hz = 0.0
rate_packets = 0
rate_start = time.monotonic()

# Display refresh
last_display_update = 0



display_fps = 0
display_frames = 0
fps_timer = time.monotonic()
# DISPLAY RENDERING
# this is for the 128x64 OLED screen i have. 
def draw_dashboard():
    display.fill(0)

    # HEADER
    connected = (
        last_packet_time is not None
        and time.monotonic() - last_packet_time < 0.75
    )
    #display.text("Sick ass telemetry", 0, 0, 1)
    display.text("Telemetry", 0, 0, 1)
    display.text("FPS:{:.0f}".format(display_fps), 85, 0, 1)
    display.line(0, 9, 127, 9, 1)

    # JOYSTICK GRAPH
    # this is a box on the screen to show where the joystick is aimed. deadzone in the middle. 

    # Graph boundaries
    display.rect(1, 12, 50, 50, 1)

    # Center axes
    display.line(26, 14, 26, 59, 1)
    display.line(3, 37, 48, 37, 1)

    # Joystick center
    display.pixel(26, 37, 1)

    # Clamp coordinates for drawing
    x = max(-1.0, min(1.0, joystick_x))
    y = max(-1.0, min(1.0, joystick_y))

    # Convert coordinates into screen position
    px = int(26 + x * 20)
    py = int(37 - y * 20)

    # Draw joystick position
    display.fill_rect(px - 2, py - 2, 5, 5, 1)

    
    # TELEMETRY INFORMATION
    display.text(
        "LINK LIVE" if connected else "LINK LOST",
        57, 12, 1
    )
    
    display.text(
        "PKT {:06d}".format(packet_count % 1000000),
        57, 20, 1
    )

    # i sure hope this matches the data rate configured, rn it should be 250kbps.
    display.text(
        "RATE {:.1f}/s".format(rate_hz),
        57, 28, 1
    )

    display.text(
        "X {:+.2f}".format(joystick_x),
        57, 36, 1
    )

    display.text(
        "Y {:+.2f}".format(joystick_y),
        57, 44, 1
    )

    # the joystick module i have has a button if you press down the joystick. 
    display.text(
        "SW DOWN" if joystick_button == 0 else "SW UP",
        57, 52, 1
    )

    display.show()



# INITIAL DISPLAY
draw_dashboard()


# MAIN RECEIVER LOOP

print("Listening for joystick packets...")
async def RadioTask():
    global packet_count
    global rate_packets
    global last_packet_time
    global joystick_x
    global joystick_y
    global joystick_button
    global rate_hz
    global rate_start
    while True:

        # RECEIVE ALL AVAILABLE PACKETS
        while radio.available():
            payload = radio.read()

            if payload is None:
                continue

            if len(payload) != 12:
                print("Invalid packet size:", len(payload))
                continue

            # Decode transmitter packet
            x, y, button = struct.unpack("<ffI", payload)

            # Validate coordinates
            if not math.isfinite(x) or not math.isfinite(y):
                continue

            # Update telemetry
            joystick_x = x
            joystick_y = y
            joystick_button = button

            packet_count += 1
            rate_packets += 1
            last_packet_time = time.monotonic()

        # PACKET RATE CALCULATION
        now = time.monotonic()
        elapsed = now - rate_start

        if elapsed >= 1.0:
            rate_hz = rate_packets / elapsed
            rate_packets = 0
            rate_start = now

        # Yield to display task
        await asyncio.sleep(0.001)


async def ScreenTask():
    global last_display_update
    global display_fps, display_frames, fps_timer

    while True:
        now = time.monotonic()

        if now - last_display_update >= 0.05:
            draw_dashboard()
            last_display_update = now

            display_frames += 1

        # Calculate FPS once per second
        if now - fps_timer >= 1.0:
            display_fps = display_frames / (now - fps_timer)
            display_frames = 0
            fps_timer = now

        await asyncio.sleep(0.001)
    

async def main():
    await asyncio.gather(
        RadioTask(),
        ScreenTask()
    )

asyncio.run(main())