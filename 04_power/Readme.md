# flora2 Power Supply & Power Management

## Solar Power

https://www.waveshare.com/solar-power-manager.htm

https://www.waveshare.com/Solar-Panel-6V-5W.htm

**Note 1:**

The Solar Power Manager can supply up to 1A @5V. Please make sure that the controller (with sensors) and pump(s) do not exceed this limit.

### Battery Voltage Measurement

For battery voltage measurement, an additional wire has to be soldered to the Solar Power Manager (net label *VBAT* in the schematic). A small resistor (e.g. 10 Ohms) in series to the U_bat output should be added to avoid high currents in case of a short circuit.

On the flora2 PCB, an analog moisture input has to be used for voltage measurement. The following changes have to be made to adapt the battery voltage to the Analog-to-Digital Converter (ADC) input voltage range (see [Schematic](https://github.com/matthias-bs/Flora2/blob/main/08_hardware/flora2_sch.pdf)).

**Moisture4 Input -> U_bat Input**

<table>
  <tr>
    <th>Part
    <th>Value for Moisture4
    <th>Value for U_bat
  </tr>
  <tr>
    <td>R16
    <td>220k
    <td>200k
  </tr>
    <tr>
    <td>R17
    <td>330k || 100nF
    <td>100k || 100nF
  </tr>
</table>
