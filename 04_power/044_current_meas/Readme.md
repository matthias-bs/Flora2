# Measurements


## Setup
![current_measurement_setup](https://user-images.githubusercontent.com/83612361/128756903-79873bf0-8608-4d68-a2b8-82456bac1f63.png)
[Probe Image: https://commons.wikimedia.org/wiki/File:WTPC_Oscilloscope-1.jpg]

Shunt: Vishay RS-2C 0,1 Ohm / 0,5% / 2,5W
Marker: J9/Pin 9 - GPIO 0 (Pullup)

## PicoSope Settings
Ch A +/- 500mV DC
Ch B +/- 5V DC
50 s/div

Trigger B, rising edge, 1,0V 5%
Measurements: Ch A - DC Average - Between Rulers

[20210613-flora2o.pssettings](https://github.com/matthias-bs/Flora2/blob/main/04_power/044_current_meas/20210613-flora2o.pssettings)

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

<table>
<thead>
  <tr>
    <th>File</th>
    <th>Description</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td><a href="flora2o-20210613-pump1-avg%2Bmax.pdf" target="_blank" rel="noopener noreferrer">flora2o-20210613-pump1-avg+max.pdf</a></td>
    <td>Pump 1 on; average and max. current</td>
  </tr>
  <tr>
    <td><a href="flora2o-20210613-pump1-ec_cycle.pdf" target="_blank" rel="noopener noreferrer">flora2o-20210613-pump1-ec_cycle.pdf</a></td>
    <td>Pump 1 on; electronic commutation cycle time</td>
  </tr>
  <tr>
    <td><a href="flora2o-20210613-pump1-ec_cycle.pdf" target="_blank" rel="noopener noreferrer">flora2o-20210613-pump1-ec_cycle.pdf</a></td>
    <td>Complete cycle with pump 1 on</td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump1-total_avg.pdf</td>
    <td>Complete cycle with pump 1 on; average current</td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump2-avg+max.pdf</td>
    <td>Pump 2 on; average and max. current</td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump2-ec_cycle.pdf</td>
    <td>Pump 2 on; electronic commutation cycle time<br></td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump2-total_avg.pdf</td>
    <td>Complete cycle with pump 2 on; average current</td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump_off-active.pdf</td>
    <td>Complete cycle, pumps off; average current</td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump_off-ble.pdf</td>
    <td>BLE activity; average current</td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump_off-ble_time.pdf</td>
    <td>BLE activity; communication duration<br></td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump_off-sleep_mode.pdf</td>
    <td>Sleep mode; average current</td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump_off-total_avg.pdf</td>
    <td>Complete cycle, pumps off; average current</td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump_off-wifi.pdf</td>
    <td>WiFi activity; average current</td>
  </tr>
  <tr>
    <td>flora2o-20210613-pump_off-wifi_peak.pdf</td>
    <td>WiFi activity; peak current</td>
  </tr>
  <tr>
    <td>flora2o-20210613-solar_pwr-noise.pdf</td>
    <td>Solar power supply; current noise (min./max./avg.)</td>
  </tr>
  <tr>
    <td>flora2o-20210613-solar_pwr-noise_T.pdf</td>
    <td>Solar power supply; current noise timing</td>
  </tr>
  <tr>
    <td>flora2o-20210613-solar_pwr-noise_f.pdf</td>
    <td>Solar power sopply; current noise frequency</td>
  </tr>
</tbody>
</table>
