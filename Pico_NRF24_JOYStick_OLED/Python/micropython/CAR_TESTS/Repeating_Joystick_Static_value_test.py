from machine import Pin, SPI
from nrf24l01 import NRF24L01
import time
import struct

led = Pin(25, Pin.OUT)

spi = SPI(0, sck=Pin(2), mosi=Pin(3), miso=Pin(0))
csn = Pin(5, mode=Pin.OUT, value=1)
ce  = Pin(4, mode=Pin.OUT, value=0)

radio = NRF24L01(spi, csn, ce, channel=75, payload_size=12)
radio.stop_listening()
radio.flush_tx()
radio.set_power_speed(6, 0x00)  # 0dBm, 1Mbps
radio.reg_write(0x01, 0x00)     # disable auto-ack
radio.reg_write(0x04, 0x00)     # disable retries
radio.open_tx_pipe(b'\xe1\xf0\xf0\xf0\xf0')   # transmit to car
radio.open_rx_pipe(1, b'\xd2\xf0\xf0\xf0\xf0')

print("rf_setup:", hex(radio.reg_read(0x06)))
print("config:  ", hex(radio.reg_read(0x00)))
print("channel: ", hex(radio.reg_read(0x05)))
print("test transmitter started")

data_buffer = bytearray(12)
cnt = 0

while True:
    # Send a simple repeating pattern: x=0.5, y=0.5, sw=1.0
    x_val = 0.5
    y_val = 0.5
    s_val = 1.0

    struct.pack_into('!f', data_buffer, 0, x_val)
    struct.pack_into('!f', data_buffer, 4, y_val)
    struct.pack_into('!f', data_buffer, 8, s_val)

    radio.stop_listening()
    radio.reg_write(0x00, 0x0e)  # TX mode with CRC
    try:
        radio.send(data_buffer)
        led(1)
        print('sent', cnt)
    except OSError:
        led(0)
        print('fail', cnt)

    radio.reg_write(0x00, 0x0f)  # back to RX mode
    ce(1)
    time.sleep_ms(30)
    cnt += 1