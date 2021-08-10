# LTspice Simulation of Sensor Power Circuit (Q3/Q4)

## Introduction

The LTspice simulation was done, because the sensor power circuit initially did not work. It proved that the circuit was designed properly. Further investigation revealed the Q4 footprint mismatch (see https://github.com/matthias-bs/Flora2/blob/main/08_hardware/Readme.md). 

## Setup

<table>
<thead>
  <tr>
    <th>File</th>
    <th>Description</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td>ZVN4206A.net</td>
    <td>ZETEX ZVN4206A spice model (from https://www.diodes.com/part/view/ZVN4206A)</td>
  </tr>
  <tr>
    <td>ZVP2106A.net</td>
    <td>ZETEX ZVP2106A spice model (from https://www.diodes.com/part/view/ZVP2106A)</td>
  </tr>
  <tr>
    <td>ZVN4206A.asy</td>
    <td>LTspice symbol for ZVN4206A (using ZVN4206A model file)</td>
  </tr>
  <tr>
    <td>ZVP2106A.asy</td>
    <td>LTspice symbol for ZVP2106A (using ZVP2106A model file)</td>
  </tr>
  <tr>
    <td>sensor_pwr.net</td>
    <td>Netlist</td>
  </tr>
  <tr>
    <td>sensor_pwr.asc</td>
    <td>LTspice schematic</td>
  </tr>
  <tr>
    <td>sensor_pwr.plt</td>
    <td>LTspice plot parameters</td>
  </tr>
  <tr>
    <td>sensor_pwr.pdf</td>
    <td>Simulation plot (PDF)</td>
  </tr>
</tbody>
</table>


## Schematic
<img width="586" alt="sensor_pwr_schematic" src="https://user-images.githubusercontent.com/83612361/128794531-4419c104-c65a-4cee-8f37-7fe8dccd86cc.png">

Sensor Power Switch Circuit (Load: 50 Ohms)

<img width="586" alt="sensor_pwr_w_parameter_schematic" src="https://user-images.githubusercontent.com/83612361/128792654-e2c411ed-5fd3-4f14-a2c7-b1b869227a97.png">

Sensor Power Switch Circuit (Load: [45 50 55 500] Ohms)

## Simulation Results

<img width="294" alt="sensor_pwr_plt" src="https://user-images.githubusercontent.com/83612361/128793739-cfc6fc4d-47fd-4cd2-9eb2-ae2ab9a9db51.png">

Simulation Plot (Load: 50 Ohms)
