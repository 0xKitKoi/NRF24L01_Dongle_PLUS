# Pico nRF24 + SSD1306 C SDK receiver

A C implementation of the CircuitPython joystick receiver.

## Wiring

### SSD1306 I2C OLED
- SDA -> GP18
- SCL -> GP19
- VCC -> 3V3 (or the module's supported supply)
- GND -> GND

### nRF24L01+
- SCK -> GP2
- MOSI -> GP3
- MISO -> GP0
- CSN -> GP7
- CE -> GP4
- VCC -> regulated 3.3V
- GND -> GND

## Radio compatibility

The receiver is configured for:
- Channel 75
- 250 kbps
- -12 dBm
- 16-bit CRC
- 5-byte address `1Node`
- RX pipe 1
- Fixed 12-byte payload: little-endian `float x`, `float y`, `uint32_t button`
- Auto-ACK disabled

## Build

This project expects the Raspberry Pi Pico C/C++ SDK to be installed and `PICO_SDK_PATH` configured.

```sh
mkdir build
cd build
cmake ..
make -j4
```
## Notes

- Core 0 continuously services the nRF24 RX FIFO.
- Core 1 renders the OLED dashboard.
- A mutex protects telemetry shared between cores.
- OLED I2C is configured at 1 MHz. If the display is unstable, change `i2c_init(OLED_I2C, 1000 * 1000)` to `i2c_init(OLED_I2C, 400 * 1000)`.
- The OLED renderer targets about 10 refreshes/second. Actual FPS is printed over USB serial.
- This is a minimal self-contained SSD1306 driver and 5x7 font, not an Adafruit library dependency.
