while(1):
    printf("bruh")

import board
import busio
import digitalio
import struct
import time

from circuitpython_nrf24l01.rf24 import RF24

ADDRESS = b"1Node"

spi = busio.SPI(
    clock=board.GP2,
    MOSI=board.GP3,
    MISO=board.GP0
)

csn = digitalio.DigitalInOut(board.GP5)
csn.direction = digitalio.Direction.OUTPUT
csn.value = True

ce = digitalio.DigitalInOut(board.GP4)
ce.direction = digitalio.Direction.OUTPUT
ce.value = False

radio = RF24(spi, csn, ce)

radio.channel = 75
radio.data_rate = 250
radio.pa_level = -12
radio.crc = 2
radio.address_length = 5

radio.auto_ack = False
radio.dynamic_payloads = True

radio.open_rx_pipe(1, ADDRESS)
radio.listen = True

print("RX ready")

while True:
    if radio.available():
        payload = radio.read()

        if payload is not None:
            print("RAW:", payload.hex())

            if len(payload) == 12:
                x, y, count = struct.unpack("<ffI", payload)

                print("X:", x)
                print("Y:", y)
                print("Count:", count)
                print("----------------")
            else:
                print("Unexpected payload length:", len(payload))

    time.sleep(0.005)
