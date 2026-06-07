# Flora2Arduino — Implementation Plan

Port of `09_software/_main.py` (MicroPython) to an Arduino/C++ sketch targeting the
ESP32 DevKit.

---

## Goals

| # | Goal |
|---|------|
| 1 | Preserve all run-time behaviour of the MicroPython version |
| 2 | Keep module boundaries so each subsystem is independently testable |
| 3 | Compile-time feature flags replace the `config.ini` `[...]_en` booleans |
| 4 | `RTC_DATA_ATTR` replaces `machine.RTC().memory()` for deep-sleep persistence |
| 5 | MQTT (arduino-mqtt) + optional HA discovery replaces `paho-mqtt` |

---

## Target Hardware

| Signal | GPIO | Notes |
|--------|------|-------|
| Moisture sensor 1 | 34 | ADC1 ch6, input-only |
| Moisture sensor 2 | 36 | ADC1 ch0 (SVP), input-only — avoids GPIO 35 conflict |
| Moisture sensor 3 | 32 | ADC1 ch4 |
| Moisture sensor 4 | 33 | ADC1 ch5 |
| Pump relay 1 | 19 | HIGH = on |
| Pump relay 2 | 18 | HIGH = on |
| Tank LOW switch | 23 | HIGH = triggered |
| Tank EMPTY switch | 21 | HIGH = triggered |
| Sensor power rail | 27 | HIGH = VCC on (I2C + 1-Wire) |
| DS18B20 OneWire | 5 | Optional |
| I2C SDA | 26 | ENV III / BME280 |
| I2C SCL | 25 | ENV III / BME280 |
| Battery ADC | 35 | ADC1 ch7, 100 kΩ / 200 kΩ divider → 1/3 of V_BAT |

---

## File Layout

```
Flora2Arduino/
├── Flora2Arduino.ino       Main sketch (setup / loop)
├── Flora2Cfg.h             GPIO pins, feature flags, compile-time defaults,
│                           PlantSensorData + WeatherData structs
├── secrets.h               WiFi network array, MQTT credentials, TIMEZONE_STR,
│                           NTP server list  (not committed)
├── secrets.h.example       Template for secrets.h
├── data/
│   └── config.json         Runtime config (uploaded to LittleFS)
└── src/
    ├── ConfigLoader.h/.cpp  Load AppConfig from LittleFS JSON, with defaults
    ├── Tank.h/.cpp          TankStatus (OK/LOW/EMPTY) from two GPIO inputs
    ├── Pump.h/.cpp          Timed relay with tank-abort + MQTT keep-alive CB
    ├── MoistureSensor.h/.cpp analogReadMilliVolts() → % (linear calibration)
    ├── DS1820.h/.cpp        OneWireNg_CurrentPlatform + DSTherm driver (Placeholder, no global ctor)
    ├── WeatherSensor.h/.cpp  ENV III (SHT3X + QMP6988) or BME280, I2C
    ├── MiFloraSensor.h/.cpp  NimBLE passive scan + TheengsDecoder + GATT battery
    ├── Irrigation.h/.cpp     Auto/manual irrigation logic
    ├── WiFiManager.h/.cpp    Multi-network connect, NTP sync
    └── MqttManager.h/.cpp    MQTT pub/sub, LWT, optional HA discovery
```

---

## Required Libraries

| Library | Author | Purpose |
|---------|--------|---------|
| NimBLE-Arduino v2 | h2zero | BLE passive scan + GATT client |
| TheengsDecoder | theengs | Decode raw MiFlora advertisement JSON |
| ArduinoJson | bblanchon | config.json parsing, TheengsDecoder |
| arduino-mqtt | 256dpi | MQTT client (MQTTClient) |
| OneWireNg | pstolarz | 1-Wire bus driver + DS18xx `DSTherm` driver |
| M5Unit-ENV | m5stack | SHT3X + QMP6988 (`#ifdef WEATHER_SENSOR_ENV3`) |
| pocketBME280 | angrest | BME280 (`#ifdef WEATHER_SENSOR_BME280`) |

---

## Feature Flags (`Flora2Cfg.h`)

| Flag | Effect |
|------|--------|
| `WEATHER_SENSOR_ENV3` | Include M5Unit-ENV driver (SHT3X + QMP6988) |
| `WEATHER_SENSOR_BME280` | Include Adafruit BME280 driver |
| `TEMPERATURE_SENSOR_EN` | Enable DS18B20 ambient temperature |
| `BATTERY_VOLTAGE_EN` | Enable battery ADC measurement |
| `MQTT_TLS_EN` | Use `WiFiClientSecure` + `/ca.crt` from LittleFS |
| `HA_DISCOVERY_EN` | Publish HA MQTT auto-discovery on first boot |

---

## Deep-Sleep Persistence (`RTC_DATA_ATTR`)

MicroPython uses `machine.RTC().memory()` with a packed struct.  
Arduino uses `RTC_DATA_ATTR` static variables in IRAM:

| Variable | Type | Purpose |
|----------|------|---------|
| `rtc_pump_last_run[2]` | `time_t` | Last successful pump run timestamp |
| `rtc_auto_irr_enabled` | `bool` | Auto irrigation on/off (MQTT controllable) |
| `rtc_sleep_disabled` | `bool` | Suppress deep sleep (MQTT controllable) |
| `rtc_man_irr_duration` | `uint32_t` | Manual irrigation duration (MQTT settable) |
| `rtc_cycle_count` | `uint32_t` | Wakeup counter (NTP re-sync trigger) |
| `rtc_first_boot` | `bool` | Clear `gSensorData[]` on first power-on |

---

## `ConfigLoader` — `AppConfig` Structure

Loaded from `data/config.json` via LittleFS.  Falls back silently to compile-time
defaults when the file is absent or a key is missing.

```
AppConfig
├── GeneralConfig
│   ├── processing_period / processing_period2 (s)
│   ├── battery_weak (mV) — switch to period2
│   ├── battery_low  (mV) — force 1-hour deep sleep
│   ├── deep_sleep / auto_irrigation
│   ├── irr_duration_auto[2], irr_duration_man (s)
│   ├── irr_rest (s) — minimum rest between irrigations
│   ├── night_begin/night_end (hr + min)
│   ├── sensor_batt_low (%)
│   └── ble_batt_interval (cycles)
├── SensorConfig
│   ├── sensor_interface: BLE | LOCAL | MQTT
│   ├── temperature_sensor, weather_sensor, battery_voltage (bool)
├── MqttConfig
│   ├── base_topic_flora, base_topic_sensors
│   ├── message_timeout (s), keepalive (s)
└── PlantConfig[5]
    ├── id, address (BLE MAC), name
    ├── pump (1-based), adc_pin (-1 = N/A)
    ├── temp_min/max, cond_min/max (µS/cm)
    ├── moist_min/lo/hi/max (%)
    └── light_min/irr/max (lux)
```

---

## `MiFloraSensor` — BLE Design

1. **Passive scan** via `NimBLEScan` for `BLE_SCAN_TIME` seconds.  
   Raw advertisement bytes are stored in a callback (no decoding during ISR).
2. **Post-scan decoding** with `TheengsDecoder::decodeBLEJson()`.  
   Each MiFlora advertisement carries exactly one property:  
   `tempc` | `moi` | `lux` | `fer` → mapped to `MIFLORA_VALID_*` bitmask bits.
3. **Smart early stop**: scan terminates as soon as all sensors in the address list
   have `valid_mask == MIFLORA_VALID_ALL (0x0F)`.
4. **GATT battery read** (every `ble_batt_interval` cycles):  
   Connect to each sensor, read characteristic `0x1a02`.  
   Results cached in NVS `Preferences` namespace `"mf_batt"` so a failed GATT read
   does not erase the last known value.

---

## `MqttManager` — MQTT Design

- Library: **arduino-mqtt** (256dpi), `MQTTClient`.
- LWT: `{base_topic_flora}/status` = `"dead"`, retain, QoS 1.  
  Published `"alive"` on connect.
- Subscribed topics: manual irrigate command, auto-irrigate enable, sleep disable,
  manual duration, incoming sensor data (MQTT sensor mode).
- **Pending-state pattern**: MQTT callback writes to `pendingXxx` fields; `loop()`
  processes them in the main thread (no shared-state races).
- Optional HA auto-discovery (`#ifdef HA_DISCOVERY_EN`): published once on
  `rtc_cycle_count == 0`.

---

## Main Loop (`loop()`)

| Step | Action |
|------|--------|
| 1 | Sensor power rail ON, 200 ms warm-up |
| 2 | Read weather sensor (ENV III / BME280) |
| 3 | Read DS18B20 ambient temperature (`#ifdef TEMPERATURE_SENSOR_EN`) |
| 4 | Plant sensor data: BLE passive scan **or** local ADC **or** (pending MQTT) |
| 5 | WiFi connect + periodic NTP re-sync (every 48 cycles ≈ 12 h at 15-min period) |
| 6 | MQTT connect → process incoming messages → publish all sensor data |
| 7 | Manual irrigation (MQTT-commanded) |
| 8 | Auto irrigation (threshold + night window + rest period) |
| 9 | Sensor power rail OFF |
| 10 | Increment `rtc_cycle_count`, enter deep sleep or busy-wait |

Battery below `battery_low` → skip everything, sleep 1 h.  
Battery below `battery_weak` → use `processing_period2` (longer interval).

---

## `Irrigation` — Decision Logic

```
autoIrrigate(plant i):
  skip if: night window active
  skip if: time(now) - rtc_pump_last_run[pump] < irr_rest
  skip if: moisture >= moist_min
  skip if: light > light_irr  (bright conditions)
  skip if: tank EMPTY
  RUN pump for irr_duration_auto[pump] seconds (or until tank LOW)
  SET rtc_pump_last_run[pump] = time(now)
```

---

## Secrets File (`secrets.h`)

```cpp
// WiFi networks (tried in order)
static const WifiCreds_t WIFI_NETWORKS[] = {
    { "SSID1", "pass1" },
    { "SSID2", "pass2" },
};
static const char MQTT_HOST[] = "broker.example.com";
static const uint16_t MQTT_PORT = 1883;
static const char MQTT_USER[] = "flora2";
static const char MQTT_PASS[] = "secret";
static const char TIMEZONE_STR[] = "CET-1CEST,M3.5.0,M10.5.0/3";
static const char NTP_SERVER_1[] = "pool.ntp.org";
static const char NTP_SERVER_2[] = "time.google.com";
static const char NTP_SERVER_3[] = "";
```

---

## LittleFS Upload

Upload `data/config.json` (and optionally `data/ca.crt` for TLS) with the
**Arduino LittleFS Upload** plugin for the Arduino IDE, or via `arduino-cli`:

```
arduino-cli upload --fqbn esp32:esp32:esp32 --port /dev/ttyUSB0 \
    --input-file build/flora2arduino.ino.bin
# then upload filesystem image separately with esptool or the IDE plugin
```

---

## Known Design Decisions / Deviations from MicroPython

| Topic | MicroPython | Arduino |
|-------|-------------|---------|
| Deep-sleep persistence | `machine.RTC().memory()` + `struct.pack` | `RTC_DATA_ATTR` |
| BLE | `micropython-bluetooth` + raw GAP | NimBLE-Arduino v2 |
| MQTT | `umqtt.robust` | arduino-mqtt (256dpi) |
| Config | `config.ini` + `ConfigParser` | `config.json` + ArduinoJson |
| Weather sensor | `bme280.py` / `qmp6988.py` | M5Unit-ENV / pocketBME280 (angrest) |
| GPIO 35 conflict | Both `UBATT_ADC` and `moisture[1]` on 35 | Moisture[1] moved to GPIO 36 |
| DS1820 | `temperature.py` (DS18B20 via OneWire) | `OneWireNg_CurrentPlatform` + `DSTherm` (pstolarz); `Placeholder<>` avoids global construction |

---

## Session Updates (2026-06-01)

Recent implementation and debugging changes made while porting and validating the Arduino sketch.

- BLE: Removed passive advertisement-based MiFlora decoding and `TheengsDecoder` dependency. Replaced with reliable direct GATT reads (write control char, short delay, read data char).
- MiFlora: GATT read sequence implemented; RSSI captured; battery readings cached in NVS (`Preferences`) so failed reads do not erase last-known battery values.
- MQTT: Topics and payloads adjusted — plant sensors published under `{base_topic_flora}/sensor/{id}`, and `lux` renamed to `light` in JSON payloads. Added more verbose publish diagnostics (logs publish result, `_client.lastError()`/`returnCode()`).
- Timezone / NTP: `TIMEZONE_STR` default located in `Flora2Cfg.h`; `setenv("TZ", TIMEZONE_STR, 1); tzset();` now executed in `setup()` every boot so deep-sleep cycles observe correct localtime/DST.
- Pump last-run timestamps: `publishPumpLastRun()` added (epoch + ISO8601). Guarding added to avoid recording any pump `last_run` when system time is not yet NTP-synced (prevents bogus epochs like 970). The device logs a warning instead.
- Weather sensor (ENV III): `WeatherSensor` now logs an I²C bus scan when init fails and probes the hardware-reported addresses (SHT3x at 0x44, QMP6988 observed at 0x70 on some modules). Code uses single fixed hardware addresses.
- ArduinoJson: Deprecated `containsKey()` calls replaced with safe checks using `.isNull()` / `.as<T>()`.
- Cleanup: Removed stale passive-scan defines and `TheengsDecoder` from `package.json`; added I²C scan helper and other small diagnostic helpers.

Pending items / follow-ups:

- Gather full serial logs for a complete connect/publish/disconnect cycle to diagnose intermittent MQTT publish failures (WiFi association drops observed).  
- Optionally add build-time control to suppress NimBLE debug logs and document usage.  
- If you prefer to record event timestamps even when NTP is not yet available, we can implement a provisional RTC/monotonic mapping to convert later after sync — advise if desired.

