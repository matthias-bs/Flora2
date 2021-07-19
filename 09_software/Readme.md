# flora2 Software

## Open Issues

- Sending Email reports works only partly (depending on configuration)

    Sending Email works only if sufficient memory is available due to the relative high SSL memory requirements. For example, a configuration with three analog moisture sensor leaves enough memory, another with two Miflora BLE sensor does not. At least the program handles the out-of-memory exception gracefully.

- Secure MQTT (MQTT over TLS) is kind of buggy

    As far as the MicroPython documentation goes, using the SSL Socket Wrapper or not should not make a big difference (except for memory requirements). But in fact it does! It seems the SSL Socket Object behaves different from the normal SSL Sockets regarding exceptions and polling. I racked my brain for quite a while to pin down the problem and to find a solution - to no avail yet. The current workaround is still not convincing.
    
- Compatibility to CPython / Raspberry Pi broken

    At some point, compatibility was left behind due to tweaking the code to run on **MicroPython / ESP32** - and partly in favor of new features. With some efforts, it should be possible to re-establish compatibility to **CPython / Raspberry Pi**. As a first step, the code could be modified to run on **MicroPython / Raspberry Pi**.
    The sources are quite cluttered with conditional sections concerning MicroPython and ESP32. GPIO handling is one of the inglorious examples...


Some minor points:
- Night Time Detection deserves some clean-up
- Logging / Debug Printing depending on VERBOSITY could be improved
- Wi-Fi Manager integration failed due to lack of memory


## Files

<table>
<thead>
  <tr>
    <th>File</th>
    <th>Description</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td>adc1_cal.py</td>
    <td>MicroPython ESP32 ADC1 conversion using V_ref calibration value</td>
  </tr>
  <tr>
    <td>alert.py</td>
    <td>Alert class; detects Changes / Range Violations of Sensor Data and System Status, implements filter to control frequency of Email Reports</td>
  </tr>
  <tr>
    <td>bme280.py</td>
    <td>BME280 Temperature/Barometric Pressure/Humidity Sensor Library</td>
  </tr>
  <tr>
    <td>boot.py</td>
    <td>Empty MicroPython Boot Code</td>
  </tr>
  <tr>
    <td>ConfigParser.py</td>
    <td>Minimal and Functional Version of CPython's ConfigParser Module</td>
  </tr>
  <tr>
    <td>config.ini</td>
    <td><b>User's Configuration File</b></td>
  </tr>
  <tr>
    <td>config.py</td>
    <td><b>Default application settings and the Settings class with attributes from the configuration file</b></td>
  </tr>
  <tr>
    <td>flora_email.py</td>
    <td>Email class; a wrapper around umail or email.message, respectively</td>
  </tr>
  <tr>
    <td>flora_mqtt.py</td>
    <td>flora2 MQTT functions</td>
  </tr>
  <tr>
    <td>garbage_collect.py</td>
    <td>gcollect() and meminfo() Helper Functions</td>
  </tr>
  <tr>
    <td>gpio.py</td>
    <td>A stub (i.e. non-functional(!) replacement) for RPi.GPIO on other systems than Raspberry Pi</td>
  </tr>
  <tr>
    <td>irrigation.py</td>
    <td>Irrigation class; manual and automatic Irrigation</td>
  </tr>
  <tr>
    <td>main.py</td>
    <td>flora2 Main Code</td>
  </tr>
  <tr>
    <td>miflora.py</td>
    <td>MicroPython Library for Xiaomi Mi Flora (aka. flower care) BLE Plant Sensors</td>
  </tr>
  <tr>
    <td>moisture.py</td>
    <td>Moisture class; analog Moisture Sensor Reading</td>
  </tr>
  <tr>
    <td>print_line.py</td>
    <td>print_line() function; printing with time stamp and some formatting</td>
  </tr>
  <tr>
    <td>pump.py</td>
    <td>Pump class; Pump hardware control/status, software busy flag and timestamp</td>
  </tr>
  <tr>
    <td>report.py</td>
    <td>Report class; generates HTML report with various sensor/plant and system data</td>
  </tr>
  <tr>
    <td>secrets.py</td>
    <td><b>User defined constants to be kept secret</b></td>
  </tr>
  <tr>
    <td>sensor_power.py</td>
    <td>Sensor_Power class; controls the sensor power via GPIO</td>
  </tr>
  <tr>
    <td>sensor.py</td>
    <td>Sensor class; stores sensor and plant data, compares sensor data with plant data and checks sensor battery and data validity</td>
  </tr>
  <tr>
    <td>tank.py</td>
    <td>Tank class; tank fill level status values <low> and <empty> according to sensor outputs via GPIO pins</td>
  </tr>
  <tr>
    <td>temperature.py</td>
    <td>MicroPython Temperature class; DS18x20 OneWire Temperature Sensor Value</td>
  </tr>
  <tr>
    <td>umail.py</td>
    <td>uMail (MicroMail) for MicroPython</td>
  </tr>
  <tr>
    <td>weather.py</td>
    <td>Weather Sensor Data; temperature, humidity and barometric pressure from BME280 sensor connected to I2C bus interface</td>
  </tr>
  <tr>
    <td>wifi.py</td>
    <td>WiFi Connection Functions</td>
  </tr>
</tbody>
</table>
