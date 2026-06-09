###############################################################################
# main.py
# Plant monitoring and irrigation system - simplified (no MQTT)
#
# - reads Mi Flora BLE plant sensors  OR  local analog moisture sensors
# - reads optional weather sensor (BME280 / SHT30+QMP6988)
# - reads optional DS1820 one-wire temperature sensor
# - controls water pumps for automatic irrigation
# - monitors water tank fill level
# - logs all data via serial console
#
# WiFi is used only once at startup for NTP time synchronisation, then
# deactivated to free IDF heap for BLE (ESP32 cannot run both at the same
# time with the available RAM budget).
#
# Sensor interfaces supported: 'ble', 'local'
# ('mqtt' is not supported in this simplified variant - use _main.py instead)
#
# created: 05/2026 updated: 05/2026
#
# This program is Copyright (C) 05/2026 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20260530 Simplified from main.py (_main.py):
#          - WiFi used only for NTP time sync at boot, then deactivated
#          - MQTT removed entirely
#          - Manual irrigation removed (no remote control without MQTT)
#          - All sensor data logged to serial console via print_line()
#
###############################################################################

import sys
import binascii
import struct
import time
from time import sleep

import machine
import ntptime
import uerrno
from machine import reset
if sys.implementation.name == "micropython":
    import gc
if sys.platform == "esp32":
    import adc1_cal

from wifi import wifi_manager

# Flora specific modules
import config as cfg
from config import MEMINFO, VERBOSITY
from garbage_collect import gcollect, meminfo

import irrigation as m_irrigation
import moisture as m_moisture
from print_line import print_line
import pump as m_pump
import sensor as s
import sensor_power as m_sensor_power
import tank as m_tank
import temperature as m_temperature
import weather as m_weather


###############################################################################
# Central European Time including daylight saving (UTC+1 / UTC+2)
# Valid 1996-2099
###############################################################################
def cettime():
    year = time.localtime()[0]
    HHMarch   = time.mktime((year, 3,  (31 - (int(5 * year / 4 + 4)) % 7), 1, 0, 0, 0, 0, 0))
    HHOctober = time.mktime((year, 10, (31 - (int(5 * year / 4 + 1)) % 7), 1, 0, 0, 0, 0, 0))
    now = time.time()
    if now < HHMarch:
        return time.localtime(now + 3600)   # CET  UTC+1
    elif now < HHOctober:
        return time.localtime(now + 7200)   # CEST UTC+2
    else:
        return time.localtime(now + 3600)   # CET  UTC+1


# Magic header stored as first 2 bytes of RTC memory to detect valid data.
_RTC_MAGIC = b'F2'
_RTC_FMT   = '>2sII'  # magic(2) + ts_pump0(4) + ts_pump1(4) = 10 bytes


def _rtc_load_timestamps():
    """Restore pump last-run timestamps from RTC memory after deep sleep.

    Returns a list [ts_pump0, ts_pump1] of Unix timestamps (int).
    Returns [0, 0] when no valid data is present (first boot or power-off).
    """
    try:
        raw = machine.RTC().memory()
        if len(raw) >= struct.calcsize(_RTC_FMT):
            magic, ts0, ts1 = struct.unpack_from(_RTC_FMT, raw)
            if magic == _RTC_MAGIC:
                print_line(f'RTC memory: restored pump timestamps {ts0}, {ts1}')
                return [ts0, ts1]
    except Exception:  # noqa: BLE001
        pass
    print_line('RTC memory: no valid timestamps — using 0')
    return [0, 0]


def _rtc_save_timestamps():
    """Persist current pump last-run timestamps to RTC memory before deep sleep."""
    ts0 = m_pump.pumps[0].timestamp if m_pump.pumps[0] else 0
    ts1 = m_pump.pumps[1].timestamp if m_pump.pumps[1] else 0
    try:
        machine.RTC().memory(struct.pack(_RTC_FMT, _RTC_MAGIC, ts0, ts1))
        print_line(f'RTC memory: saved pump timestamps {ts0}, {ts1}')
    except Exception:  # noqa: BLE001
        print_line('RTC memory: save failed', error=True)


###############################################################################
# main
###############################################################################
def main():
    if MEMINFO:
        meminfo('Boot begin')

    # ------------------------------------------------------------------
    # WiFi: connect for NTP only
    # ------------------------------------------------------------------
    wifi_ok = wifi_manager.connect()
    if wifi_ok:
        print_line('WiFi ready (NTP sync).')
    else:
        print_line(f'WiFi connection failed - clock will not be synchronised.', error=True)

    if sys.implementation.name == "micropython":
        gc.enable()  # pylint: disable=possibly-used-before-assignment
        gc.threshold(gc.mem_free() // 2 + gc.mem_alloc())  # pylint: disable=no-member

    if MEMINFO:
        meminfo('Boot finished')

    # ------------------------------------------------------------------
    # NTP time sync
    # ------------------------------------------------------------------
    if wifi_ok:
        ntp_ok = False
        for _ntp_attempt in range(3):
            try:
                ntptime.settime()
                ntp_ok = True
                break
            except OSError:
                sleep(2)

        if ntp_ok:
            tm = cettime()
            machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))
            print_line(f'NTP Time: {tm[0]}/{tm[1]:02}/{tm[2]:02} {tm[3]:02}:{tm[4]:02}:{tm[5]:02}')
        else:
            print_line('NTP sync failed after 3 attempts - continuing with unsynchronised clock.', error=True)

        # Tear WiFi down cleanly before BLE / main work starts.
        # A short sleep lets lwIP release all TCP/IP buffers back to the IDF heap;
        # without it esp_wifi_stop() may malloc-fail and trigger a LoadProhibited crash.
        sleep(2)
        wifi_manager.deinit()
        gcollect()
        print_line('WiFi deactivated.')

    if MEMINFO:
        meminfo('After NTP / WiFi deinit')

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    config_dir = './'
    print(cfg.PROJECT_NAME)
    print(cfg.PROJECT_VERSION)
    print(cfg.PROJECT_BUILD)
    print('Source:', cfg.PROJECT_URL)

    cfg.settings = cfg.Settings(config_dir, delimiters=('=',), inline_comment_prefixes=('#'))

    if cfg.settings.sensor_interface == 'mqtt':
        print_line('sensor_interface=mqtt is not supported in this simplified build.', error=True)
        print_line('Use _main.py (full-featured version with MQTT) instead.', error=True)
        sys.exit(1)

    # ------------------------------------------------------------------
    # BLE imports (deferred: after config to avoid OOM before Settings)
    # ------------------------------------------------------------------
    if cfg.settings.sensor_interface == 'ble':
        import miflora  # noqa: F401
        from miflora import Mi_Flora
        from bluetooth import BLE

    # ------------------------------------------------------------------
    # Battery voltage check (early exit to deep sleep if critically low)
    # ------------------------------------------------------------------
    sleep_duration = cfg.settings.processing_period

    if cfg.settings.battery_voltage:
        ubatt = adc1_cal.ADC1Cal(  # pylint: disable=E0601
            machine.Pin(cfg.UBATT_ADC_PIN), cfg.UBATT_DIV, cfg.VREF, cfg.UBATT_SAMPLES, "ADC1_Calibrated")
        ubatt.atten(machine.ADC.ATTN_6DB)
        print_line(f'Battery Voltage: {ubatt.voltage:4} mV')

        if ubatt.voltage < cfg.settings.battery_weak:
            sleep_duration = cfg.settings.processing_period2
        else:
            sleep_duration = cfg.settings.processing_period

        # Critically low: skip processing entirely and sleep
        if (ubatt.voltage < cfg.settings.battery_low) and (ubatt.voltage > 1000):
            del ubatt
            del cfg.settings
            print_line('Low voltage - entering deep sleep.')
            _rtc_save_timestamps()
            machine.deepsleep(sleep_duration * 1000)
            while True:
                pass  # not reached

    # ------------------------------------------------------------------
    # Hardware objects
    # ------------------------------------------------------------------
    sensor_power = m_sensor_power.SensorPower(cfg.GPIO_SENSOR_POWER)
    m_tank.tank  = m_tank.Tank(cfg.GPIO_TANK_SENS_LOW, cfg.GPIO_TANK_SENS_EMPTY)
    for i in range(2):
        m_pump.pumps[i] = m_pump.Pump(cfg.GPIO_PUMP_POWER[i], cfg.GPIO_PUMP_STATUS[i], m_tank.tank)

    # Restore irrigation timestamps that survived the previous deep sleep
    if sys.platform == 'esp32':
        _ts = _rtc_load_timestamps()
        m_pump.pumps[0].timestamp = _ts[0]
        m_pump.pumps[1].timestamp = _ts[1]

    # ------------------------------------------------------------------
    # Sensor objects
    # ------------------------------------------------------------------
    sensor_list = cfg.settings.plant_sensors.split(',')
    if not sensor_list or sensor_list == ['']:
        print_line('No sensors found in [Sensors] section of "config.ini".', error=True, sd_notify=True)
        sys.exit(1)

    s.sensors = {}
    gcollect()

    for sensor in sensor_list:
        s.sensors[sensor] = s.Sensor(sensor, cfg.settings.mqtt_msg_timeout, cfg.settings.sensor_batt_low)
        if not cfg.settings.cp.has_section(sensor):
            print_line(f'config.ini: sensor "{sensor}" listed under [Sensors] but has no config section.', error=True, sd_notify=True)
            sys.exit(1)

    for sensor in s.sensors:
        if s.config_error(sensor):
            sys.exit(1)
        s.sensors[sensor].init_plant()
        if cfg.settings.sensor_interface == 'ble':
            addr = cfg.settings.cp.get(sensor, 'address').replace(':', '')
            s.sensors[sensor].address = binascii.unhexlify(addr)
        cfg.settings.cp.remove_section(sensor)

    del cfg.settings.cp
    gcollect()

    # ------------------------------------------------------------------
    # Local (analog) moisture sensor interface
    # ------------------------------------------------------------------
    if cfg.settings.sensor_interface == 'local':
        if len(sensor_list) > len(cfg.MOISTURE_ADC_PINS):
            print_line('Number of sensors exceeds available MOISTURE_ADC_PINS in config.py.', error=True, sd_notify=True)
            sys.exit(1)
        moisture = {}
        for i, sensor in enumerate(sensor_list):
            moisture[sensor] = m_moisture.Moisture(cfg.MOISTURE_ADC_PINS[i], cfg.MOISTURE_MIN_VAL, cfg.MOISTURE_MAX_VAL)

    # ------------------------------------------------------------------
    # Irrigation controller
    # ------------------------------------------------------------------
    irrigation = m_irrigation.Irrigation()

    if MEMINFO:
        meminfo('Start Main Loop')
    print_line('Start Main Loop.')

    ###########################################################################
    # Main execution loop
    ###########################################################################
    while True:

        # ------------------------------------------------------------------
        # BLE plant sensors
        # ------------------------------------------------------------------
        if cfg.settings.sensor_interface == 'ble':
            # Sleep lets the IDF heap settle after any previous BLE/WiFi activity
            # before esp_bt_controller_init() tries to allocate its host task stack.
            sleep(2)
            gcollect()
            if MEMINFO:
                meminfo('Before BLE init')

            ble = None
            try:
                ble = BLE()
                miflora_ble = Mi_Flora(ble)
            except OSError as exc:
                print_line(f'BLE init failed: {uerrno.errorcode[exc.errno]}', error=True, sd_notify=True)
                print_line('Cannot access MiFlora sensor(s) this cycle.')
            else:
                for sensor in s.sensors:
                    addr = s.sensors[sensor].address
                    print_line(f'Connecting to MiFlora {binascii.hexlify(addr)} ({sensor}) ...')

                    read_ok = False
                    for _attempt in range(cfg.BLE_MAX_RETRIES):
                        miflora_ble.gap_connect(miflora.ADDR_TYPE_PUBLIC, addr)
                        if miflora_ble.wait_for(miflora.S_READ_SENSOR_DONE, cfg.BLE_TIMEOUT):
                            print_line(f'  [{sensor}] Battery:      {miflora_ble.battery} %')
                            print_line(f'  [{sensor}] Temperature:  {miflora_ble.temp} °C')
                            print_line(f'  [{sensor}] Light:        {miflora_ble.light} lx')
                            print_line(f'  [{sensor}] Moisture:     {miflora_ble.moist} %')
                            print_line(f'  [{sensor}] Conductivity: {miflora_ble.cond} µS/cm')
                            s.sensors[sensor].update_sensor(
                                miflora_ble.temp, miflora_ble.cond,
                                miflora_ble.moist, miflora_ble.light,
                                miflora_ble.battery)
                            read_ok = True
                            break
                        else:
                            print_line(f'  [{sensor}] Read failed (attempt {_attempt + 1}/{cfg.BLE_MAX_RETRIES})')

                    if not read_ok:
                        print_line(f'  [{sensor}] All retries exhausted.', error=True)

                    miflora_ble.disconnect()
                    if miflora_ble.wait_for_connection(False, cfg.BLE_TIMEOUT):
                        print_line(f'  [{sensor}] Disconnected.')
                    else:
                        print_line(f'  [{sensor}] Disconnect timed out - resetting BLE state.', error=True)
                        miflora_ble._reset()  # pylint: disable=W0212

                del miflora_ble

            if ble is not None:
                del ble
            gcollect()

        # ------------------------------------------------------------------
        # Sensor power on (controls I2C / 1-wire supply on ESP32)
        # ------------------------------------------------------------------
        if sys.platform == "esp32":
            sensor_power.enable(True)
            sleep(1)

        # ------------------------------------------------------------------
        # Local (analog) moisture sensors
        # ------------------------------------------------------------------
        if cfg.settings.sensor_interface == 'local':
            for sensor in sensor_list:
                valid, moist_val = moisture[sensor].moisture
                if valid:
                    s.sensors[sensor].update_moisture_sensor(moist_val)
                    print_line(f'[{sensor}] Moisture: {moist_val} %')
                else:
                    print_line(f'[{sensor}] Moisture sensor out of range (raw={moist_val}). '
                               f'Check wiring and power.', error=True, sd_notify=True)

        # ------------------------------------------------------------------
        # DS1820 one-wire temperature sensor (optional)
        # ------------------------------------------------------------------
        if cfg.settings.temperature_sensor:
            temperature = m_temperature.Temperature(cfg.GPIO_TEMP_SENS)
            if temperature.devices > 0:
                temp = temperature.temperature()
                if cfg.settings.sensor_interface == 'local':
                    for sensor in s.sensors:
                        s.sensors[sensor].update_temperature_sensor(temp)
                print_line(f'DS1820 Temperature: {temp:.1f} °C')
            else:
                print_line('DS1820: no devices found.', error=True)
            del temperature
            gcollect()

        # ------------------------------------------------------------------
        # Weather sensor (BME280 / SHT30+QMP6988, optional)
        # ------------------------------------------------------------------
        if cfg.settings.weather_sensor:
            valid, weather_reading = m_weather.weather_data()
            if valid:
                print_line(f'Weather: '
                           f'Temperature={weather_reading["temperature"]:.1f}°C  '
                           f'Humidity={weather_reading["humidity"]:.1f}%  '
                           f'Pressure={weather_reading["pressure"]:.1f}hPa')
            else:
                print_line('Weather sensor: no valid data.', error=True)
            del weather_reading

        # ------------------------------------------------------------------
        # Battery voltage (optional)
        # ------------------------------------------------------------------
        if cfg.settings.battery_voltage:
            ubatt = adc1_cal.ADC1Cal(
                machine.Pin(cfg.UBATT_ADC_PIN), cfg.UBATT_DIV, cfg.VREF, cfg.UBATT_SAMPLES, "ADC1_Calibrated")
            ubatt.atten(machine.ADC.ATTN_6DB)
            print_line(f'Battery Voltage: {ubatt.voltage:4} mV')

        # ------------------------------------------------------------------
        # Tank status
        # ------------------------------------------------------------------
        _TANK_LABELS = ('OK', 'LOW', 'EMPTY')
        tank_status = m_tank.tank.status
        print_line(f'Tank: {_TANK_LABELS[tank_status] if tank_status < len(_TANK_LABELS) else "?"}')

        # ------------------------------------------------------------------
        # Sensor summary (verbose)
        # ------------------------------------------------------------------
        if VERBOSITY > 0:
            for sensor in s.sensors:
                if s.sensors[sensor].valid:
                    print_line(f'[{sensor}] '
                               f'Moist={s.sensors[sensor].moist:3d}%  '
                               f'Temp={s.sensors[sensor].temp:5.1f}°C  '
                               f'Cond={s.sensors[sensor].cond:4d}µS/cm  '
                               f'Light={s.sensors[sensor].light:6d}lx  '
                               f'Batt={s.sensors[sensor].batt:3d}%')
                else:
                    print_line(f'[{sensor}] No valid data yet.')

        # ------------------------------------------------------------------
        # Automatic irrigation
        # ------------------------------------------------------------------
        if cfg.settings.auto_irrigation:
            cfg.settings.irr_scheduled = irrigation.auto_irrigation()

        # ------------------------------------------------------------------
        # Sensor power off
        # ------------------------------------------------------------------
        if sys.platform == "esp32":
            sensor_power.enable(False)

        gcollect()
        if MEMINFO:
            meminfo('End of loop')

        # ------------------------------------------------------------------
        # Sleep / deep sleep
        # ------------------------------------------------------------------
        if cfg.settings.daemon_enabled:
            if sys.platform == "esp32" and cfg.settings.deep_sleep:
                # Only deep-sleep when battery voltage measurement is either
                # disabled or reports a plausible voltage (> 1 V), to allow
                # easy flashing when no battery is connected.
                _do_deepsleep = (not cfg.settings.battery_voltage or
                                 (cfg.settings.battery_voltage and ubatt.voltage > 1000))  # pylint: disable=possibly-used-before-assignment
                if _do_deepsleep:
                    print_line(f'Entering deep sleep for {sleep_duration} s ...')
                    _rtc_save_timestamps()
                    del sensor_power
                    del m_tank.tank
                    del m_pump.pumps
                    try:
                        del moisture  # pylint: disable=possibly-used-before-assignment
                    except NameError:
                        pass
                    del s.sensors
                    del cfg.settings
                    machine.deepsleep(sleep_duration * 1000)
                    while True:
                        pass  # not reached

            if cfg.settings.battery_voltage:
                del ubatt  # pylint: disable=possibly-used-before-assignment

            print_line(f'Standby ({cfg.settings.processing_period} s) ...')
            sleep(cfg.settings.processing_period)

        else:
            print_line('Finished (non-daemon mode).')
            break


###############################################################################
# Entry point
###############################################################################
if __name__ == '__main__':
    main()
