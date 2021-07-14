# flora2 - Hardware

## Bugs

- Distance between D1-4 and nearby resistors too small
- U1 (voltage regulator) blocks access to Micro-USB connector
- PCB for case "BOPLA EM 220 F" too wide
  
  B_actual:  75,5
  
  B_target: 73,0
  
- No mounting holes for case "BOPLA EM 220 F"
- Wrong footprint for U1 ESP32 DevKit
  
  B_actual:  22,86mm (fits HiLetgo ESP-32S!)
  
  B_target: 25,25mm (fits AZ-Delivery ESP32-DevKitC V4/JoyIt NodeMCU ESP32)
  
- Wrong footprint for Q4 ZVP2106A (**see patch p1**)
- Add pull-down resistor 10 kOhm at gate of Q3, otherwise Sensor_PWR_int wpuld be active in Deep-Sleep-Mode (**see patch p1**)

**Patch p1**
![Patch p1](08_hardware/flora2_pcb_v1.0p1_patch_q4.png)

## Open Issues
- add capacitors 100nF parallel to ADC inputs
- add voltage divider for Ubatt measurement as assembly option: R10=200k, R11=100k (opt.) 
- add DS18B20 + pull-up resistor 4k7 (opt.)
- add pull-down resistors for pump drivers (opt.)
- reduce Standby-Power in Deep-Sleep-Mode (opt.)
    - remove R10 or LED2 (red) from ESP-32S module
