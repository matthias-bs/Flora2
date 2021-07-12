# Measurements


## Setup
https://commons.wikimedia.org/wiki/File:WTPC_Oscilloscope-1.jpg

Shunt: Vishay RS-2C 0,1 Ohm / 0,5% / 2,5W
Marker: J9/Pin 9 - GPIO 0 (Pullup)

## PicoSope Settings
Ch A +/- 500mV DC
Ch B +/- 5V DC
50 s/div

Trigger B, rising edge, 1,0V 5%
Measurements: Ch A - DC Average - Between Rulers

## SW Marker

<table>
<tr>
    <th>Marker<th>Level<th>Code Section
</tr>
<tr>
    <td>#0<td>1<td>Boot done
</tr>
<tr>
    <td>#1<td>0<td>WiFi on
</tr>
<tr>
    <td>#2<td>1<td>MQTT init done
</tr>
<tr>
    <td>#3<td>0<td>Start main loop
</tr>
<tr>
    <td>#4<td>1<td>BLE start
</tr>
<tr>
    <td>#5<td>0<td>BLE end
</tr>
<tr>
    <td>#6<td>1<td>Deep sleep (Pull up)
</tr>
</table>
  
## Results

flora2o-20210613-pump_off-final

- AVG (-0.05  ;0:00  ) = 3,26 mA (Deep Sleep)
- AVG ( 0:00  ;1:02  ) = 76 mA (active)
- AVG ( 0:08  ;0:09.3) = 100 mA (max. WiFi activity)
- AVG ( 0:24.3;0:46.2) = 92 mA (BLE active)
