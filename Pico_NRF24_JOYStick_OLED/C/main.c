#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>

#include "pico/stdlib.h"
#include "pico/multicore.h"
#include "pico/mutex.h"
#include "hardware/i2c.h"
#include "hardware/spi.h"
#include "hardware/gpio.h"

// ---------------- Pin configuration ----------------
#define OLED_I2C       i2c1
#define OLED_SDA       18
#define OLED_SCL       19
#define OLED_ADDR      0x3C

#define NRF_SPI        spi0
#define NRF_SCK        2
#define NRF_MOSI       3
#define NRF_MISO       0
#define NRF_CSN        7
#define NRF_CE         4

// ---------------- nRF24L01+ registers/commands ----------------
#define NRF_REG_CONFIG       0x00
#define NRF_REG_EN_AA        0x01
#define NRF_REG_EN_RXADDR    0x02
#define NRF_REG_SETUP_AW     0x03
#define NRF_REG_SETUP_RETR   0x04
#define NRF_REG_RF_CH        0x05
#define NRF_REG_RF_SETUP     0x06
#define NRF_REG_STATUS       0x07
#define NRF_REG_RX_ADDR_P1   0x0B
#define NRF_REG_RX_PW_P1     0x12
#define NRF_REG_FIFO_STATUS  0x17

#define NRF_CMD_R_REGISTER   0x00
#define NRF_CMD_W_REGISTER   0x20
#define NRF_CMD_R_RX_PAYLOAD 0x61
#define NRF_CMD_FLUSH_RX     0xE2
#define NRF_CMD_NOP          0xFF

#define NRF_STATUS_RX_DR     0x40
#define NRF_STATUS_RX_P_NO   0x0E
#define NRF_FIFO_RX_EMPTY    0x01

#define OLED_W 128
#define OLED_H 64
#define OLED_BUF_SIZE (OLED_W * OLED_H / 8)

typedef struct {
    float x;
    float y;
    uint32_t button;
    uint32_t packets;
    uint32_t rate_hz;
    absolute_time_t last_packet;
    bool ever_received;
} telemetry_t;

static telemetry_t telemetry = {0};
static mutex_t telemetry_mutex;

static uint8_t framebuffer[OLED_BUF_SIZE];
static uint8_t oled_tx[OLED_BUF_SIZE + 1];

// ---------------- nRF24 low-level SPI ----------------
static inline void nrf_csn(bool high) { gpio_put(NRF_CSN, high); }
static inline void nrf_ce(bool high)  { gpio_put(NRF_CE, high); }

static uint8_t nrf_transfer(uint8_t value) {
    uint8_t rx = 0xFF;
    spi_write_read_blocking(NRF_SPI, &value, &rx, 1);
    return rx;
}

static uint8_t nrf_read_reg(uint8_t reg) {
    uint8_t value;
    nrf_csn(false);
    nrf_transfer(NRF_CMD_R_REGISTER | (reg & 0x1F));
    value = nrf_transfer(NRF_CMD_NOP);
    nrf_csn(true);
    return value;
}

static void nrf_write_reg(uint8_t reg, uint8_t value) {
    nrf_csn(false);
    nrf_transfer(NRF_CMD_W_REGISTER | (reg & 0x1F));
    nrf_transfer(value);
    nrf_csn(true);
}

static void nrf_write_buf(uint8_t reg, const uint8_t *data, size_t len) {
    nrf_csn(false);
    nrf_transfer(NRF_CMD_W_REGISTER | (reg & 0x1F));
    for (size_t i = 0; i < len; ++i) nrf_transfer(data[i]);
    nrf_csn(true);
}

static void nrf_command(uint8_t command) {
    nrf_csn(false);
    nrf_transfer(command);
    nrf_csn(true);
}

static bool nrf_init(void) {
    uint8_t address[5] = {'1', 'N', 'o', 'd', 'e'};

    nrf_ce(false);
    sleep_ms(100);

    // Power down while configuring.
    nrf_write_reg(NRF_REG_CONFIG, 0x0C); // EN_CRC + 16-bit CRC
    nrf_write_reg(NRF_REG_EN_AA, 0x00);  // Auto-ACK disabled
    nrf_write_reg(NRF_REG_EN_RXADDR, 0x02); // Enable pipe 1
    nrf_write_reg(NRF_REG_SETUP_AW, 0x03);  // 5-byte address
    nrf_write_reg(NRF_REG_SETUP_RETR, 0x00);
    nrf_write_reg(NRF_REG_RF_CH, 75);
    nrf_write_reg(NRF_REG_RF_SETUP, 0x22); // 250 kbps, -12 dBm
    nrf_write_buf(NRF_REG_RX_ADDR_P1, address, sizeof(address));
    nrf_write_reg(NRF_REG_RX_PW_P1, 12);   // Fixed 12-byte payload
    nrf_write_reg(NRF_REG_STATUS, 0x70);   // Clear IRQ flags
    nrf_command(NRF_CMD_FLUSH_RX);

    // Power up, CRC enabled, receiver mode.
    nrf_write_reg(NRF_REG_CONFIG, 0x0F);
    sleep_ms(2);
    nrf_ce(true);
    sleep_ms(2);

    // Basic sanity check: register values should read back.
    return nrf_read_reg(NRF_REG_RF_CH) == 75 &&
           nrf_read_reg(NRF_REG_SETUP_AW) == 0x03;
}

static bool nrf_read_packet(float *x, float *y, uint32_t *button) {
    uint8_t status = nrf_read_reg(NRF_REG_STATUS);
    uint8_t fifo = nrf_read_reg(NRF_REG_FIFO_STATUS);

    if ((status & NRF_STATUS_RX_DR) == 0 && (fifo & NRF_FIFO_RX_EMPTY)) {
        return false;
    }

    // Read all pending payloads in the main loop; this function reads one.
    uint8_t payload[12];
    nrf_csn(false);
    nrf_transfer(NRF_CMD_R_RX_PAYLOAD);
    for (int i = 0; i < 12; ++i) payload[i] = nrf_transfer(NRF_CMD_NOP);
    nrf_csn(true);

    nrf_write_reg(NRF_REG_STATUS, NRF_STATUS_RX_DR);

    memcpy(x, &payload[0], sizeof(float));
    memcpy(y, &payload[4], sizeof(float));
    memcpy(button, &payload[8], sizeof(uint32_t));

    return isfinite(*x) && isfinite(*y);
}

// ---------------- OLED driver ----------------
static void oled_command(uint8_t cmd) {
    uint8_t data[2] = {0x00, cmd};
    i2c_write_blocking(OLED_I2C, OLED_ADDR, data, 2, false);
}

static void oled_init(void) {
    const uint8_t init_seq[] = {
        0xAE,       // display off
        0xD5, 0x80, // clock divide
        0xA8, 0x3F, // multiplex 1/64
        0xD3, 0x00, // display offset
        0x40,       // start line
        0x8D, 0x14, // charge pump
        0x20, 0x00, // horizontal addressing
        0xA1,       // segment remap
        0xC8,       // COM scan direction
        0xDA, 0x12, // COM pins
        0x81, 0x7F, // contrast
        0xD9, 0xF1, // pre-charge
        0xDB, 0x40, // VCOM detect
        0xA4,       // resume RAM display
        0xA6,       // normal display
        0xAF        // display on
    };
    for (size_t i = 0; i < sizeof(init_seq); ++i) oled_command(init_seq[i]);
    memset(framebuffer, 0, sizeof(framebuffer));
}

static void oled_show(void) {
    // Set full-screen column/page window.
    oled_command(0x21); oled_command(0); oled_command(127);
    oled_command(0x22); oled_command(0); oled_command(7);

    oled_tx[0] = 0x40; // GDDRAM data
    memcpy(&oled_tx[1], framebuffer, OLED_BUF_SIZE);

    // Single 1025-byte I2C transaction.
    i2c_write_blocking(OLED_I2C, OLED_ADDR, oled_tx, sizeof(oled_tx), false);
}

static void pixel(int x, int y, bool on) {
    if (x < 0 || x >= OLED_W || y < 0 || y >= OLED_H) return;
    size_t index = (size_t)x + (size_t)(y / 8) * OLED_W;
    uint8_t mask = (uint8_t)(1u << (y & 7));
    if (on) framebuffer[index] |= mask;
    else framebuffer[index] &= (uint8_t)~mask;
}

static void fill_screen(bool on) {
    memset(framebuffer, on ? 0xFF : 0x00, sizeof(framebuffer));
}

static void line(int x0, int y0, int x1, int y1, bool on) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    while (true) {
        pixel(x0, y0, on);
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

static void rect(int x, int y, int w, int h, bool on) {
    line(x, y, x + w - 1, y, on);
    line(x, y, x, y + h - 1, on);
    line(x + w - 1, y, x + w - 1, y + h - 1, on);
    line(x, y + h - 1, x + w - 1, y + h - 1, on);
}

static void fill_rect(int x, int y, int w, int h, bool on) {
    for (int yy = y; yy < y + h; ++yy)
        for (int xx = x; xx < x + w; ++xx)
            pixel(xx, yy, on);
}

// Compact 5x7 font. Each byte is one vertical column, LSB at the top.
static const uint8_t *glyph(char c) {
    static const uint8_t blank[5] = {0,0,0,0,0};
    #define G(ch,a,b,c_,d,e) case ch: { static const uint8_t v[5]={a,b,c_,d,e}; return v; }
    if (c >= 'a' && c <= 'z') c = (char)(c - 'a' + 'A');
    switch (c) {
        G('A',0x7E,0x11,0x11,0x11,0x7E)
        G('B',0x7F,0x49,0x49,0x49,0x36)
        G('C',0x3E,0x41,0x41,0x41,0x22)
        G('D',0x7F,0x41,0x41,0x22,0x1C)
        G('E',0x7F,0x49,0x49,0x49,0x41)
        G('F',0x7F,0x09,0x09,0x09,0x01)
        G('G',0x3E,0x41,0x49,0x49,0x7A)
        G('H',0x7F,0x08,0x08,0x08,0x7F)
        G('I',0x00,0x41,0x7F,0x41,0x00)
        G('J',0x20,0x40,0x41,0x3F,0x01)
        G('K',0x7F,0x08,0x14,0x22,0x41)
        G('L',0x7F,0x40,0x40,0x40,0x40)
        G('M',0x7F,0x02,0x0C,0x02,0x7F)
        G('N',0x7F,0x04,0x08,0x10,0x7F)
        G('O',0x3E,0x41,0x41,0x41,0x3E)
        G('P',0x7F,0x09,0x09,0x09,0x06)
        G('Q',0x3E,0x41,0x51,0x21,0x5E)
        G('R',0x7F,0x09,0x19,0x29,0x46)
        G('S',0x46,0x49,0x49,0x49,0x31)
        G('T',0x01,0x01,0x7F,0x01,0x01)
        G('U',0x3F,0x40,0x40,0x40,0x3F)
        G('V',0x1F,0x20,0x40,0x20,0x1F)
        G('W',0x3F,0x40,0x38,0x40,0x3F)
        G('X',0x63,0x14,0x08,0x14,0x63)
        G('Y',0x07,0x08,0x70,0x08,0x07)
        G('Z',0x61,0x51,0x49,0x45,0x43)
        G('0',0x3E,0x51,0x49,0x45,0x3E)
        G('1',0x00,0x42,0x7F,0x40,0x00)
        G('2',0x42,0x61,0x51,0x49,0x46)
        G('3',0x21,0x41,0x45,0x4B,0x31)
        G('4',0x18,0x14,0x12,0x7F,0x10)
        G('5',0x27,0x45,0x45,0x45,0x39)
        G('6',0x3C,0x4A,0x49,0x49,0x30)
        G('7',0x01,0x71,0x09,0x05,0x03)
        G('8',0x36,0x49,0x49,0x49,0x36)
        G('9',0x06,0x49,0x49,0x29,0x1E)
        G('-',0x08,0x08,0x08,0x08,0x08)
        G('+',0x08,0x08,0x3E,0x08,0x08)
        G('.',0x00,0x60,0x60,0x00,0x00)
        G(':',0x00,0x36,0x36,0x00,0x00)
        G('/',0x20,0x10,0x08,0x04,0x02)
        G('!',0x00,0x00,0x5F,0x00,0x00)
        G('?',0x02,0x01,0x51,0x09,0x06)
        G(' ',0,0,0,0,0)
        default: return blank;
    }
    #undef G
}

static void text(int x, int y, const char *s, bool on) {
    while (*s) {
        const uint8_t *g = glyph(*s++);
        for (int col = 0; col < 5; ++col)
            for (int row = 0; row < 7; ++row)
                if (g[col] & (1u << row)) pixel(x + col, y + row, on);
        x += 6;
    }
}

// ---------------- Dashboard / rendering ----------------
static void draw_dashboard(float x, float y, uint32_t button, uint32_t packets,
                           uint32_t rate, bool connected, float fps) {
    char buf[24];
    fill_screen(false);

    text(0, 1, "SCUZZY RADIO", true);
    snprintf(buf, sizeof(buf), "FPS:%02.0f", fps);
    text(84, 1, buf, true);
    line(0, 9, 127, 9, true);

    rect(1, 12, 50, 50, true);
    line(26, 14, 26, 59, true);
    line(3, 37, 48, 37, true);
    pixel(26, 37, true);

    if (!isfinite(x)) x = 0;
    if (!isfinite(y)) y = 0;
    if (x < -1) x = -1; if (x > 1) x = 1;
    if (y < -1) y = -1; if (y > 1) y = 1;
    int px = (int)(26 + x * 20);
    int py = (int)(37 - y * 20);
    fill_rect(px - 2, py - 2, 5, 5, true);

    text(57, 12, connected ? "LINK LIVE" : "LINK LOST", true);
    snprintf(buf, sizeof(buf), "PKT %06lu", (unsigned long)(packets % 1000000));
    text(57, 20, buf, true);
    snprintf(buf, sizeof(buf), "RATE %lu/S", (unsigned long)rate);
    text(57, 28, buf, true);
    snprintf(buf, sizeof(buf), "X %+0.2f", x);
    text(57, 36, buf, true);
    snprintf(buf, sizeof(buf), "Y %+0.2f", y);
    text(57, 44, buf, true);
    text(57, 52, button == 0 ? "SW DOWN" : "SW UP", true);

    oled_show();
}

// ---------------- Tasks ----------------
static void display_core(void) {
    oled_init();

    absolute_time_t fps_window = get_absolute_time();
    uint32_t frames = 0;
    float fps = 0.0f;

    while (true) {
        telemetry_t snapshot;

        mutex_enter_blocking(&telemetry_mutex);
        snapshot = telemetry;
        mutex_exit(&telemetry_mutex);

        bool connected = snapshot.ever_received &&
            absolute_time_diff_us(snapshot.last_packet, get_absolute_time()) < 750000;

        absolute_time_t start = get_absolute_time();
        draw_dashboard(snapshot.x, snapshot.y, snapshot.button,
                       snapshot.packets, snapshot.rate_hz, connected, fps);
        absolute_time_t end = get_absolute_time();

        (void)start;
        (void)end;
        frames++;

        int64_t window_us = absolute_time_diff_us(fps_window, end);
        if (window_us >= 1000000) {
            fps = (float)frames * 1000000.0f / (float)window_us;
            frames = 0;
            fps_window = end;
            printf("OLED FPS: %.2f\n", fps);
        }

        // Dashboard target ~10 FPS. Actual FPS is printed above.
        sleep_ms(1);
        while (absolute_time_diff_us(end, get_absolute_time()) < 100000) {
            tight_loop_contents();
        }
    }
}

static void radio_core(void) {
    uint32_t rate_packets = 0;
    absolute_time_t rate_window = get_absolute_time();

    while (true) {
        // Drain all available RX FIFO payloads.
        while (true) {
            float x, y;
            uint32_t button;

            if (!nrf_read_packet(&x, &y, &button)) break;

            mutex_enter_blocking(&telemetry_mutex);
            telemetry.x = x;
            telemetry.y = y;
            telemetry.button = button;
            telemetry.packets++;
            telemetry.last_packet = get_absolute_time();
            telemetry.ever_received = true;
            mutex_exit(&telemetry_mutex);

            rate_packets++;
        }

        absolute_time_t now = get_absolute_time();
        int64_t elapsed = absolute_time_diff_us(rate_window, now);
        if (elapsed >= 1000000) {
            uint32_t rate = (uint32_t)((double)rate_packets * 1000000.0 / (double)elapsed);
            mutex_enter_blocking(&telemetry_mutex);
            telemetry.rate_hz = rate;
            mutex_exit(&telemetry_mutex);

            rate_packets = 0;
            rate_window = now;
        }

        tight_loop_contents();
    }
}

int main(void) {
    stdio_init_all();
    sleep_ms(1500);
    printf("Scuzzy nRF24 + SSD1306 receiver starting\n");

    mutex_init(&telemetry_mutex);

    // I2C OLED.
    i2c_init(OLED_I2C, 1000 * 1000); // 1 MHz; use 400000 if your module is unstable.
    gpio_set_function(OLED_SDA, GPIO_FUNC_I2C);
    gpio_set_function(OLED_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(OLED_SDA);
    gpio_pull_up(OLED_SCL);

    // SPI nRF24.
    spi_init(NRF_SPI, 1000 * 1000);
    gpio_set_function(NRF_SCK, GPIO_FUNC_SPI);
    gpio_set_function(NRF_MOSI, GPIO_FUNC_SPI);
    gpio_set_function(NRF_MISO, GPIO_FUNC_SPI);

    gpio_init(NRF_CSN);
    gpio_set_dir(NRF_CSN, GPIO_OUT);
    gpio_put(NRF_CSN, 1);

    gpio_init(NRF_CE);
    gpio_set_dir(NRF_CE, GPIO_OUT);
    gpio_put(NRF_CE, 0);

    sleep_ms(100);

    if (!nrf_init()) {
        printf("ERROR: nRF24 did not respond. Check wiring/power.\n");
        while (true) tight_loop_contents();
    }

    printf("nRF24 ready: channel 75, 250 kbps, -12 dBm, address 1Node\n");
    printf("Launching OLED renderer on core 1\n");

    multicore_launch_core1(display_core);

    // Core 0 handles radio reception continuously.
    radio_core();
    return 0;
}
