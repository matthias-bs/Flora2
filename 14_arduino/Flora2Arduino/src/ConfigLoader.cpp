///////////////////////////////////////////////////////////////////////////////
// src/ConfigLoader.cpp
//
// Loads AppConfig from LittleFS /config.json using ArduinoJson.
// Mirrors LoadNodeCfg.cpp pattern from BresserWeatherSensorLW.
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "ConfigLoader.h"
#include <LittleFS.h>
#include <ArduinoJson.h>

#if defined(CORE_DEBUG_LEVEL) && (CORE_DEBUG_LEVEL > 0)
static const char* TAG = "ConfigLoader";
#endif
static const char* CONFIG_PATH = "/config.json";

// ─────────────────────────────────────────────────────────────────────────────
// Public
// ─────────────────────────────────────────────────────────────────────────────

bool ConfigLoader::load(AppConfig& cfg)
{
    applyDefaults(cfg);

    if (!LittleFS.begin(true)) {
        log_e("%s: LittleFS mount failed — using defaults", TAG);
        return false;
    }

    File f = LittleFS.open(CONFIG_PATH, "r");
    if (!f) {
        log_e("%s: %s not found — using defaults", TAG, CONFIG_PATH);
        return false;
    }

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, f);
    f.close();

    if (err) {
        log_e("%s: JSON parse error: %s — using defaults", TAG, err.c_str());
        return false;
    }

    // ── general ──────────────────────────────────────────────────────────────
    if (doc["general"].is<JsonObject>()) {
        JsonObject g = doc["general"];
        cfg.general.processing_period   = g["processing_period"]  | cfg.general.processing_period;
        cfg.general.processing_period2  = g["processing_period2"] | cfg.general.processing_period2;
        cfg.general.battery_weak        = g["battery_weak"]       | cfg.general.battery_weak;
        cfg.general.battery_low         = g["battery_low"]        | cfg.general.battery_low;
        cfg.general.deep_sleep          = g["deep_sleep"]         | cfg.general.deep_sleep;
        cfg.general.auto_irrigation     = g["auto_irrigation"]    | cfg.general.auto_irrigation;
        cfg.general.irr_duration_auto[0]= g["irr_duration_auto1"] | cfg.general.irr_duration_auto[0];
        cfg.general.irr_duration_auto[1]= g["irr_duration_auto2"] | cfg.general.irr_duration_auto[1];
        cfg.general.irr_duration_man    = g["irr_duration_man"]   | cfg.general.irr_duration_man;
        cfg.general.irr_rest            = g["irr_rest"]           | cfg.general.irr_rest;
        cfg.general.stale_sensor_max_age_s = g["stale_sensor_max_age_s"] | cfg.general.stale_sensor_max_age_s;
        cfg.general.sensor_batt_low     = g["sensor_batt_low"]    | cfg.general.sensor_batt_low;
        cfg.general.ble_batt_interval   = g["ble_batt_interval"]  | cfg.general.ble_batt_interval;

        const char* nb = g["night_begin"] | "22:00";
        const char* ne = g["night_end"]   | "07:00";
        parseHHMM(nb, cfg.general.night_begin_hr, cfg.general.night_begin_min);
        parseHHMM(ne, cfg.general.night_end_hr,   cfg.general.night_end_min);
    }

    // ── sensor ───────────────────────────────────────────────────────────────
    if (doc["sensor"].is<JsonObject>()) {
        JsonObject s = doc["sensor"];
        const char* si = s["sensor_interface"] | "ble";
        cfg.sensor.sensor_interface = parseSensorInterface(si);
        cfg.sensor.temperature_sensor = s["temperature_sensor"] | cfg.sensor.temperature_sensor;
        cfg.sensor.weather_sensor     = s["weather_sensor"]     | cfg.sensor.weather_sensor;
        cfg.sensor.battery_voltage    = s["battery_voltage"]    | cfg.sensor.battery_voltage;
    }

    // ── mqtt ─────────────────────────────────────────────────────────────────
    if (doc["mqtt"].is<JsonObject>()) {
        JsonObject m = doc["mqtt"];
        strlcpy(cfg.mqtt.base_topic_flora,
            m["base_topic_flora"] | cfg.mqtt.base_topic_flora,
                sizeof(cfg.mqtt.base_topic_flora));
        strlcpy(cfg.mqtt.base_topic_sensors,
            m["base_topic_sensors"] | cfg.mqtt.base_topic_sensors,
                sizeof(cfg.mqtt.base_topic_sensors));
        cfg.mqtt.message_timeout = m["message_timeout"] | cfg.mqtt.message_timeout;
        cfg.mqtt.keepalive       = m["keepalive"]       | cfg.mqtt.keepalive;
    }

    // ── plants ───────────────────────────────────────────────────────────────
    cfg.num_plants = 0;
    if (doc["plants"].is<JsonArray>()) {
        JsonArray arr = doc["plants"];
        for (JsonObject p : arr) {
            if (cfg.num_plants >= MAX_PLANT_SENSORS) {
                log_w("%s: More than %d plants in config — ignoring extras", TAG, MAX_PLANT_SENSORS);
                break;
            }
            PlantConfig& pc = cfg.plants[cfg.num_plants];

            strlcpy(pc.id,      p["id"]      | "plant", sizeof(pc.id));
            strlcpy(pc.address, p["address"] | "",      sizeof(pc.address));
            strlcpy(pc.name,    p["name"]    | pc.id,     sizeof(pc.name));
            pc.pump    = p["pump"]    | pc.pump;
            pc.adc_pin = p["adc_pin"] | pc.adc_pin;

            pc.temp_min  = p["temp_min"]  | pc.temp_min;
            pc.temp_max  = p["temp_max"]  | pc.temp_max;
            pc.cond_min  = p["cond_min"]  | pc.cond_min;
            pc.cond_max  = p["cond_max"]  | pc.cond_max;
            pc.moist_min = p["moist_min"] | pc.moist_min;
            pc.moist_lo  = p["moist_lo"]  | pc.moist_lo;
            pc.moist_hi  = p["moist_hi"]  | pc.moist_hi;
            pc.moist_max = p["moist_max"] | pc.moist_max;
            pc.light_min = p["light_min"] | pc.light_min;
            pc.light_irr = p["light_irr"] | pc.light_irr;
            pc.light_max = p["light_max"] | pc.light_max;

            cfg.num_plants++;
        }
    }

    if (cfg.num_plants == 0) {
        log_w("%s: No plants configured", TAG);
    }

    cfg.loaded_from_file = true;
    log_i("%s: Loaded %d plant(s) from %s", TAG, cfg.num_plants, CONFIG_PATH);
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Private
// ─────────────────────────────────────────────────────────────────────────────

void ConfigLoader::applyDefaults(AppConfig& cfg)
{
    memset(&cfg, 0, sizeof(cfg));

    cfg.general.processing_period    = DEF_PROCESSING_PERIOD;
    cfg.general.processing_period2   = DEF_PROCESSING_PERIOD2;
    cfg.general.battery_weak         = DEF_BATTERY_WEAK;
    cfg.general.battery_low          = DEF_BATTERY_LOW;
    cfg.general.deep_sleep           = DEF_DEEP_SLEEP;
    cfg.general.auto_irrigation      = DEF_AUTO_IRRIGATION;
    cfg.general.irr_duration_auto[0] = DEF_IRR_DURATION_AUTO1;
    cfg.general.irr_duration_auto[1] = DEF_IRR_DURATION_AUTO2;
    cfg.general.irr_duration_man     = DEF_IRR_DURATION_MAN;
    cfg.general.irr_rest             = DEF_IRR_REST;
    cfg.general.stale_sensor_max_age_s = 0;
    cfg.general.night_begin_hr       = DEF_NIGHT_BEGIN_HR;
    cfg.general.night_begin_min      = DEF_NIGHT_BEGIN_MIN;
    cfg.general.night_end_hr         = DEF_NIGHT_END_HR;
    cfg.general.night_end_min        = DEF_NIGHT_END_MIN;
    cfg.general.sensor_batt_low      = DEF_SENSOR_BATT_LOW;
    cfg.general.ble_batt_interval    = 10;

    cfg.sensor.sensor_interface  = SensorInterface::BLE;
    cfg.sensor.temperature_sensor = false;
    cfg.sensor.weather_sensor    = false;
    cfg.sensor.battery_voltage   = false;

    strlcpy(cfg.mqtt.base_topic_flora,   DEF_BASE_TOPIC_FLORA,   sizeof(cfg.mqtt.base_topic_flora));
    strlcpy(cfg.mqtt.base_topic_sensors, DEF_BASE_TOPIC_SENSORS, sizeof(cfg.mqtt.base_topic_sensors));
    cfg.mqtt.message_timeout = DEF_MESSAGE_TIMEOUT;
    cfg.mqtt.keepalive       = DEF_KEEPALIVE;

    cfg.num_plants       = 0;
    cfg.loaded_from_file = false;
}

void ConfigLoader::parseHHMM(const char* str, uint8_t& h, uint8_t& m)
{
    if (!str || strlen(str) < 4) { h = 0; m = 0; return; }
    h = (uint8_t)atoi(str);
    const char* colon = strchr(str, ':');
    m = colon ? (uint8_t)atoi(colon + 1) : 0;
}

SensorInterface ConfigLoader::parseSensorInterface(const char* str)
{
    if (strcasecmp(str, "local") == 0) return SensorInterface::LOCAL;
    if (strcasecmp(str, "mqtt")  == 0) return SensorInterface::MQTT;
    return SensorInterface::BLE;
}
