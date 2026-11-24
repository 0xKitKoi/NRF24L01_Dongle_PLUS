cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(pico_nrf24_oled C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(pico_nrf24_oled
    main.c
)

target_link_libraries(pico_nrf24_oled
    pico_stdlib
    pico_multicore
    hardware_i2c
    hardware_spi
    hardware_gpio
    hardware_sync
)

pico_enable_stdio_usb(pico_nrf24_oled 1)
pico_enable_stdio_uart(pico_nrf24_oled 0)

pico_add_extra_outputs(pico_nrf24_oled)
