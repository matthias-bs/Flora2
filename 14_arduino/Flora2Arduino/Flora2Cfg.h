///////////////////////////////////////////////////////////////////////////////
// Flora2Cfg.h
//
// Flora2 Arduino Sketch — hardware pin assignments, feature flags,
// compile-time defaults and shared data structures.
//
// Board: ESP32 DevKit (or compatible)
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>
#include <time.h>

// ─── Versioning ──────────────────────────────────────────────────────────────
#define FLORA2_VERSION "1.0.0"

// Timezone and NTP defaults (POSIX TZ format and up to 3 servers)
// Override in local build or deployment-specific headers if required.
#define TIMEZONE_STR    "CET-1CEST,M3.5.0/02:00:00,M10.5.0/03:00:00"
#define NTP_SERVER_1    "de.pool.ntp.org"
#define NTP_SERVER_2    "pool.ntp.org"
#define NTP_SERVER_3    "time.nist.gov"

// ─── Hardware — GPIO Pin Assignments ─────────────────────────────────────────

/// Battery voltage ADC — input-only GPIO35, ADC1 ch7.
/// Voltage divider: 100 kΩ to GND / 200 kΩ to VBAT → reads 1/3 of battery.
#define PIN_UBATT_ADC        35     // ADC1 ch7 (default PCB: shared with moisture sensor 2)
#define UBATT_DIV_FACTOR     3.0f   // divide-by inverse (multiply raw mV by 3)
#define UBATT_SAMPLES        10     // ADC readings to average

/// Analog capacitive moisture sensors — input-only ADC1 pins.
/// Note: On default Flora2 hardware, sensor 2 shares GPIO35 with battery ADC.
/// Using a different pin for sensor 2 or battery measurement requires a PCB patch.
#define PIN_MOISTURE_1       34     // ADC1 ch6
#define PIN_MOISTURE_2       35     // ADC1 ch7 (shared with battery voltage)
#define PIN_MOISTURE_3       32     // ADC1 ch4
#define PIN_MOISTURE_4       33     // ADC1 ch5
#define MOISTURE_SAMPLES      5     // ADC readings to average
/// Calibration: dry sensor outputs higher mV, wet sensor lower mV.
#define MOISTURE_DRY_MV    1250     // ADC mV = 0% moisture
#define MOISTURE_WET_MV     900     // ADC mV = 100% moisture

/// Pump relay outputs — HIGH = relay on = pump running.
#define PIN_PUMP_1           19
#define PIN_PUMP_2           18
#define NUM_PUMPS             2

/// Tank level switches — HIGH = switch triggered.
#define PIN_TANK_LOW         23     // Tank level low
#define PIN_TANK_EMPTY       21     // Tank empty

/// Sensor power rail — HIGH = power on (controls tank level sensor VCC).
#define PIN_SENSOR_POWER     27

/// DS1820 OneWire bus.
#define PIN_ONEWIRE           5

/// I2C bus for weather sensor.
#define PIN_I2C_SDA          26
#define PIN_I2C_SCL          25

// I2C addresses for M5Unit ENV III sensors (fixed by hardware)
// Use the device addresses reported by the hardware.
#define SHT3X_I2C_ADDR   0x44
#define QMP6988_I2C_ADDR 0x70

// ─── Feature Flags ───────────────────────────────────────────────────────────

/// Weather sensor type — define exactly one (or neither to disable).
#define WEATHER_SENSOR_ENV3       ///< M5Stack ENV III: SHT30 + QMP6988 on I2C
//#define WEATHER_SENSOR_BME280   ///< Bosch BME280 on I2C (address 0x76)

/// Enable DS1820 OneWire ambient temperature sensor.
//#define TEMPERATURE_SENSOR_EN

/// Enable battery voltage measurement via ADC.
#define BATTERY_VOLTAGE_EN

/// Enable MQTT over TLS (requires NetworkClientSecure + CA cert in LittleFS as /root_ca.pem).
//#define MQTT_TLS_EN

/// Enable Home Assistant MQTT auto-discovery messages on connect.
//#define HA_DISCOVERY_EN

// ─── Array Sizes ─────────────────────────────────────────────────────────────
#define MAX_PLANT_SENSORS    5      ///< Maximum supported plant sensors
#define MAX_WIFI_RETRIES    20      ///< Attempts before giving up WiFi
#define MQTT_BUFFER_SIZE   512      ///< MQTT message buffer in bytes

// ─── BLE Configuration ───────────────────────────────────────────────────────
// NOTE: Passive advertisement-based decoding was removed in favor of direct
// GATT reads. Keep only the GATT UUIDs and validity masks used by the code.

/// MiFlora GATT service and characteristic UUIDs.
#define MIFLORA_SVC_UUID     "00001204-0000-1000-8000-00805f9b34fb"
#define MIFLORA_BATT_CHAR    "00001a02-0000-1000-8000-00805f9b34fb"
#define MIFLORA_CTRL_CHAR    "00001a00-0000-1000-8000-00805f9b34fb"
#define MIFLORA_DATA_CHAR    "00001a01-0000-1000-8000-00805f9b34fb"

/// Valid-mask bits — each bit means that property has been received this cycle.
#define MIFLORA_VALID_TEMP   0x01
#define MIFLORA_VALID_MOI    0x02
#define MIFLORA_VALID_LUX    0x04
#define MIFLORA_VALID_FER    0x08
#define MIFLORA_VALID_ALL    0x0F

// ─── Compile-time Defaults ────────────────────────────────────────────────────
/// Used when config.json is absent or a key is missing.
#define DEF_PROCESSING_PERIOD    900
#define DEF_PROCESSING_PERIOD2  1800
#define DEF_BATTERY_WEAK        3500
#define DEF_BATTERY_LOW         3300
#define DEF_DEEP_SLEEP          true
#define DEF_AUTO_IRRIGATION     true
#define DEF_IRR_DURATION_AUTO1    30
#define DEF_IRR_DURATION_AUTO2    90
#define DEF_IRR_DURATION_MAN      60
#define DEF_IRR_REST            7200
#define DEF_NIGHT_BEGIN_HR        22
#define DEF_NIGHT_BEGIN_MIN        0
#define DEF_NIGHT_END_HR           7
#define DEF_NIGHT_END_MIN          0
#define DEF_SENSOR_BATT_LOW        5
// BLE battery interval removed; use runtime `cfg.general.ble_batt_interval` (default in ConfigLoader)
#define DEF_MESSAGE_TIMEOUT      900
#define DEF_KEEPALIVE             60
#define DEF_BASE_TOPIC_FLORA  "flora2"
#define DEF_BASE_TOPIC_SENSORS "miflora"

// ─── Shared Data Structures ───────────────────────────────────────────────────

/// Plant sensor readings collected from BLE, local ADC, or MQTT.
struct PlantSensorData {
    bool      valid;           ///< True if last_update is recent
    float     temperature;     ///< °C (from BLE or DS1820)
    uint8_t   moisture;        ///< % (from BLE or local ADC)
    uint32_t  lux;             ///< Illuminance in lux (BLE or 0 if unavailable)
    uint16_t  conductivity;    ///< Soil conductivity µS/cm (BLE or 0)
    uint8_t   battery;         ///< Sensor battery level %
    int       rssi;            ///< BLE RSSI in dBm (0 if N/A)
    time_t    last_update;     ///< Unix timestamp of last successful update
    uint8_t   valid_mask;      ///< BLE accumulator bitmask (MIFLORA_VALID_*)
};

/// Weather station readings.
struct WeatherData {
    bool  valid;
    float temperature;  ///< °C
    float humidity;     ///< %RH
    float pressure;     ///< hPa
};

// ─── Error value for DS1820 (matches driver) ─────────────────────────────
#define DEVICE_DISCONNECTED_C   -127.0f
