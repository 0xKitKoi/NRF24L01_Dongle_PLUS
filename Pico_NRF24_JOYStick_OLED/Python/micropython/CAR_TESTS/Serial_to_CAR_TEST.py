from machine import Pin, SPI
from nrf24l01 import NRF24L01
import sys
import time
import select
import struct

# --- LED ---
led = Pin(25, Pin.OUT)

# --- SPI / nRF24L01 ---
spi = SPI(0, baudrate=1_000_000, polarity=0, phase=0,
          sck=Pin(2), mosi=Pin(3), miso=Pin(0))
csn = Pin(5, Pin.OUT, value=1)
ce  = Pin(4, Pin.OUT, value=0)

# --- Radio setup ---
radio = NRF24L01(spi, csn, ce, channel=75, payload_size=12)

# Enable auto-ack + retries (IMPORTANT)
radio.reg_write(0x01, 0x3F)  # EN_AA: enable auto-ack on all pipes
radio.reg_write(0x04, 0x2F)  # SETUP_RETR: retries

radio.set_power_speed(6, 0x00)  # 0 dBm, 1 Mbps

# Pipes (must match receiver)
TX_ADDR = b'\xe1\xf0\xf0\xf0\xf0'
RX_ADDR = b'\xd2\xf0\xf0\xf0\xf0'

radio.open_tx_pipe(TX_ADDR)
#radio.open_rx_pipe(0, RX_ADDR
radio.open_rx_pipe(0, b'\xd2\xf0\xf0\xf0\xf0')  # <-- REQUIRED
radio.open_rx_pipe(1, b'\xd2\xf0\xf0\xf0\xf0')  # optional

radio.start_listening()
print("TX READY (listening + serial send enabled)")

# --- Helpers ---

def send_packet_from_line(line):
    """
    Accepts user input and sends a valid 12-byte payload.
    Format: 3 floats (x, y, s)
    Example input: 0.5 0.0 1
    """
    try:
        parts = line.strip().split()
        if len(parts) != 3:
            print("Enter: x y s  (e.g. 0.5 0.0 1)")
            return

        x = float(parts[0])
        y = float(parts[1])
        s = float(parts[2])

        payload = struct.pack('!fff', x, y, s)

        # Switch to TX
        radio.stop_listening()
        time.sleep_us(150)

        radio.send(payload)
        print("TX:", x, y, s)

    except Exception as e:
        print("TX fail:", e)

    finally:
        radio.start_listening()


# --- Main loop ---
timeout_s = 0.01

while True:
    # --- Receive packets ---
    if radio.any():
        msg = radio.recv()

        # Try decode as string first
        try:
            text = msg.rstrip(b'\0').decode()
            print("RX (text):", text)
        except:
            print("RX (raw):", msg)

    # --- Serial input ---
    if select.select([sys.stdin], [], [], timeout_s)[0]:
        line = sys.stdin.readline()
        if line:
            send_packet_from_line(line)

    # --- LED heartbeat ---
    led.toggle()
    time.sleep_ms(50)