# Raspberry Pi Pico acting as a NRF24L01 Dongle
I commonly use nrf24l01 radio modules for wireless long range communication. This specific repo is my dongle, its a device that I plug into my laptop so that I can control or listen to my other projects.
Specifically:
 My Laptop uses [this](https://github.com/0xKitKoi/Serial-Comunication-Walnut) project, It's a serial monitor I use to interface with this dongle

 my Joystick controller, see [here](https://github.com/0xKitKoi/RemoteControlledCar)

 and other battery powered pi pico's with the same nrf24 radio modules. Think of a radio mesh, devices talk to my dongle and I monitor them with this device.

![DongleImage](assets/FrontView.png)

## file struct
#### JoyStick Receiver Files
this has the most implimentations (recent testings)
##### MicroPython Files
    ./Pico_NRF24_JOYStick_OLED/Python/micropython/CAR_TESTS/Repeating_Joystick_Static_value_test.py
    ./Pico_NRF24_JOYStick_OLED/Python/micropython/CAR_TESTS/Serial_to_CAR_TEST.py
    ./Pico_NRF24_JOYStick_OLED/Python/micropython/MicroPython_SPI_Interface_with_NRF24L01_TESTER.py
##### circuitPython files
    ./Pico_NRF24_JOYStick_OLED/Python/circuitPython/Raw_Packet_Dump_Joystick_receiver.py
    ./Pico_NRF24_JOYStick_OLED/Python/circuitPython/SingleThreadedMain.py
    ./Pico_NRF24_JOYStick_OLED/Python/circuitPython/lib/circuitpython_nrf24l01/
    ./Pico_NRF24_JOYStick_OLED/Python/circuitPython/lib/adafruit_bus_device/
    ./Pico_NRF24_JOYStick_OLED/Python/circuitPython/code.py
##### C implimentations
    ./Pico_NRF24_JOYStick_OLED/C/main.c

#### Sensor Tests (CircuitPython)
    ./Sensors/AMG8833/pico_dump_amg8833_sensor.py
    ./Sensors/AMG8833/AMG8833_THERMAL_CAMERA_GRAPH.py
    ./Sensors/IMU/Display_IMU_SENSOR_main.py



# wiring
The Raspberry Pi Pico is connected to the radio module over SPI. I exposed the other GPIO pins to some female headers, so I can plug other stuff into the dongle for funsies and versatility.

    For example, the battery powered joystick controller sends the state of the Joystick, and the code here displays the joystick in a nice visual on the SSD1306 screen. 
![OptionalScreen](assets/OptionalScreenJoystickExample.png)

### other
I also have a boost converter that is optionally plugged into the VBUS pin on the pico, sharing the USB line's 5V. If i ever need to power something (say a multimeter with no 9v battery or maybe a single servo) for whatever reason, i can plug in the VIN pin of the boost converter into the female header to the right of the pico, and optionally power it. the output of the boost converter is exposed onto a female header.

![DongleBackImage](assets/BackView.png)

![OptionalSensors](assets/OptionalSensor.png)

