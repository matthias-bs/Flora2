///////////////////////////////////////////////////////////////////////////////
// src/ConfigLoader.h
//
// Loads AppConfig from LittleFS (/data/config.json).
// Falls back to compile-time defaults if the file is absent or malformed.
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>
#include "../Flora2Cfg.h"

// ─── Sensor interface mode ────────────────────────────────────────────────────
enum class SensorInterface : uint8_t {
    BLE   = 0,  ///< MiFlora BLE direct GATT read
    LOCAL = 1,  ///< Local analog moisture sensors (no BLE)
    MQTT  = 2,  ///< Receive sensor data via subscribed MQTT topics
};

// ─── Configuration Structures ─────────────────────────────────────────────────

struct GeneralConfig {
    uint32_t processing_period;         ///< Normal cycle period (s)
    uint32_t processing_period2;        ///< Low-battery cycle period (s)
    uint16_t battery_weak;              ///< Switch to period2 below (mV)
    uint16_t battery_low;               ///< Force deep sleep below (mV)
    bool     deep_sleep;
    bool     auto_irrigation;
    uint32_t irr_duration_auto[NUM_PUMPS]; ///< Auto irrigation per pump (s)
    uint32_t irr_duration_man;          ///< Manual irrigation duration (s)
    uint32_t irr_rest;                  ///< Minimum rest between irrigations (s)
    uint8_t  night_begin_hr;
    uint8_t  night_begin_min;
    uint8_t  night_end_hr;
    uint8_t  night_end_min;
    uint8_t  sensor_batt_low;           ///< Sensor low-battery threshold (%)
    uint8_t  ble_batt_interval;         ///< Reserved (legacy BLE scan mode)
};

struct SensorConfig {
    SensorInterface sensor_interface;
    bool temperature_sensor;            ///< DS1820 enabled
    bool weather_sensor;                ///< Weather sensor enabled
    bool battery_voltage;               ///< Battery ADC enabled
};

struct MqttConfig {
    char     base_topic_flora[32];      ///< Topic root for Flora2 status/control
    char     base_topic_sensors[32];    ///< Topic root for incoming sensor data
    uint32_t message_timeout;           ///< Max age of MQTT sensor data (s)
    uint32_t keepalive;                 ///< MQTT keepalive interval (s)
};

struct PlantConfig {
    char     id[32];                    ///< Unique plant identifier (used in topics)
    char     address[18];               ///< BLE MAC "XX:XX:XX:XX:XX:XX"
    char     name[32];                  ///< Human-readable plant name
    uint8_t  pump;                      ///< Pump index, 1-based (1 or 2)
    int      adc_pin;                   ///< ADC pin for LOCAL mode (-1 = N/A)
    float    temp_min;                  ///< Temperature warning low (°C)
    float    temp_max;                  ///< Temperature warning high (°C)
    uint16_t cond_min;                  ///< Conductivity warning low (µS/cm)
    uint16_t cond_max;                  ///< Conductivity warning high (µS/cm)
    uint8_t  moist_min;                 ///< Irrigate trigger: moisture below this (%)
    uint8_t  moist_lo;                  ///< Normal low moisture level (%)
    uint8_t  moist_hi;                  ///< Normal high moisture level (%)
    uint8_t  moist_max;                 ///< Emergency stop: moisture above this (%)
    uint32_t light_min;                 ///< Minimum acceptable light (lux)
    uint32_t light_irr;                 ///< Suppress irrigation above this light (lux)
    uint32_t light_max;                 ///< Overexposure warning (lux)
};

struct AppConfig {
    GeneralConfig general;
    SensorConfig  sensor;
    MqttConfig    mqtt;
    PlantConfig   plants[MAX_PLANT_SENSORS];
    uint8_t       num_plants;
    bool          loaded_from_file;     ///< True when successfully loaded from LittleFS
};

// ─── ConfigLoader ─────────────────────────────────────────────────────────────
class ConfigLoader {
public:
    /// Load from LittleFS "/config.json". Returns true on success.
    /// Always fills cfg with sensible values (defaults on failure).
    static bool load(AppConfig& cfg);

private:
    static void applyDefaults(AppConfig& cfg);
    static void parseHHMM(const char* str, uint8_t& h, uint8_t& m);
    static SensorInterface parseSensorInterface(const char* str);
};
