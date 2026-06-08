///////////////////////////////////////////////////////////////////////////////
// src/MqttManager.cpp
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "MqttManager.h"
#include <ArduinoJson.h>
#include <LittleFS.h>
#include "../secrets.h"
#include "../Flora2Cfg.h"

#if defined(CORE_DEBUG_LEVEL) && (CORE_DEBUG_LEVEL > 0)
static const char* TAG = "MqttMgr";
#endif

static constexpr uint32_t MQTT_SHUTDOWN_DRAIN_MS   = 750;
static constexpr uint32_t MQTT_DISCONNECT_WAIT_MS  = 100;

// ─────────────────────────────────────────────────────────────────────────────
// Constructor
// ─────────────────────────────────────────────────────────────────────────────

MqttManager::MqttManager(const AppConfig& cfg)
        : pendingManIrrCmd(-1),
          pendingManIrrDurationSet(false),
          pendingManIrrDuration(0),
          pendingAutoIrrSet(false),
          pendingAutoIrrValue(false),
          pendingSleepDisSet(false),
          pendingSleepDisValue(false),
          _cfg(cfg),
          _client(MQTT_BUFFER_SIZE)
{
    memset(mqttSensorData,          0, sizeof(mqttSensorData));
    memset(mqttSensorUpdated,       0, sizeof(mqttSensorUpdated));
    memset(pendingAutoIrrDurationSet, 0, sizeof(pendingAutoIrrDurationSet));
    memset(pendingAutoIrrDuration,    0, sizeof(pendingAutoIrrDuration));

    // Unique client ID: hostname + last 3 bytes of MAC
    uint64_t chipMac = ESP.getEfuseMac();
    uint8_t  mac[6]  = {
        static_cast<uint8_t>((chipMac >> 40) & 0xFF),
        static_cast<uint8_t>((chipMac >> 32) & 0xFF),
        static_cast<uint8_t>((chipMac >> 24) & 0xFF),
        static_cast<uint8_t>((chipMac >> 16) & 0xFF),
        static_cast<uint8_t>((chipMac >> 8) & 0xFF),
        static_cast<uint8_t>(chipMac & 0xFF)
    };
    snprintf(_clientId, sizeof(_clientId), "flora2_%02X%02X%02X",
             mac[3], mac[4], mac[5]);
}

// ─────────────────────────────────────────────────────────────────────────────
// connect / disconnect / loop
// ─────────────────────────────────────────────────────────────────────────────

bool MqttManager::connect()
{
#ifdef MQTT_TLS_EN
    File f = LittleFS.open("/root_ca.pem", "r");
    if (!f || !_net.loadCACert(f, f.size())) {
        log_e("%s: Failed to load CA cert", TAG);
        _net.setInsecure();
    }
    if (f) f.close();
#endif

    _client.begin(MQTT_HOST, MQTT_PORT, _net);

    // Set keepalive interval
    _client.setKeepAlive((int)_cfg.mqtt.keepalive);

    // Register message callback (lambda forwarding to member function)
    _client.onMessage([this](String& topic, String& payload) {
        onMessage(topic, payload);
    });

    // Status topic contract:
    // - "online"   while actively connected and running
    // - "sleeping" before graceful disconnect for deep sleep
    // - "dead"     via LWT when disconnect is unclean
    // Build LWT topic: {base_topic_flora}/status
    char lwtTopic[64];
    makeTopic(lwtTopic, sizeof(lwtTopic), "status");
    _client.setWill(lwtTopic, "dead", true, 1);

    log_i("%s: Connecting to %s:%d as %s", TAG, MQTT_HOST, MQTT_PORT, _clientId);

    int attempts = 0;
    while (!_client.connect(_clientId, MQTT_USERNAME, MQTT_PASSWORD)) {
        if (++attempts >= 5) {
            log_e("%s: Connection failed after %d attempts", TAG, attempts);
            return false;
        }
        log_w("%s: Retry %d/5...", TAG, attempts);
        delay(3000);
    }

    log_i("%s: Connected", TAG);
    publishStatus("online");

    // ── Subscribe to control topics ───────────────────────────────────────
    char topic[80];
    makeTopic(topic, sizeof(topic), "man_irr_cmd");
    _client.subscribe(topic, 1);

    makeTopic(topic, sizeof(topic), "man_irr_duration_ctrl");
    _client.subscribe(topic, 1);

    makeTopic(topic, sizeof(topic), "auto_irr_ctrl");
    _client.subscribe(topic, 1);

    makeTopic(topic, sizeof(topic), "sleep_dis_ctrl");
    _client.subscribe(topic, 1);

    makeTopic(topic, sizeof(topic), "auto_irr_duration1_ctrl");
    _client.subscribe(topic, 1);

    makeTopic(topic, sizeof(topic), "auto_irr_duration2_ctrl");
    _client.subscribe(topic, 1);

    // MQTT sensor interface: subscribe to each plant's topic
    if (_cfg.sensor.sensor_interface == SensorInterface::MQTT) {
        for (uint8_t i = 0; i < _cfg.num_plants; i++) {
            snprintf(topic, sizeof(topic), "%s/%s",
                     _cfg.mqtt.base_topic_sensors,
                     _cfg.plants[i].id);
            _client.subscribe(topic, 0);
            log_i("%s: Subscribed to %s", TAG, topic);
        }
    }

    return true;
}

void MqttManager::disconnect()
{
    if (!_client.connected()) return;

    // Graceful shutdown: publish terminal status and allow network processing
    // so the retained status and MQTT DISCONNECT frame have time to leave
    // before WiFi is torn down. Too-short drains can make the broker treat
    // the session as unclean and fire the LWT ("dead").
    publishStatus("sleeping", true);
    uint32_t start = millis();
    while ((millis() - start) < MQTT_SHUTDOWN_DRAIN_MS && _client.connected()) {
        _client.loop();
        delay(10);
    }

    _net.flush();
    _client.disconnect();
    _net.flush();
    delay(MQTT_DISCONNECT_WAIT_MS);
    log_i("%s: Disconnected", TAG);
}

bool MqttManager::loop()
{
    return _client.loop();
}

bool MqttManager::isConnected()
{
    return _client.connected();
}

// ─────────────────────────────────────────────────────────────────────────────
// Publish helpers
// ─────────────────────────────────────────────────────────────────────────────

void MqttManager::publishStatus(const char* status, bool retain)
{
    char topic[64];
    makeTopic(topic, sizeof(topic), "status");
    publishRetain(topic, status, retain, 1);
}

void MqttManager::publishBattery(uint32_t voltage_mV)
{
    char topic[64], payload[16];
    makeTopic(topic, sizeof(topic), "ubatt");
    snprintf(payload, sizeof(payload), "%lu", (unsigned long)voltage_mV);
    publishRetain(topic, payload, true);
}

void MqttManager::publishTank(uint8_t statusCode)
{
    // Python-compatible numeric encoding: 0=empty, 1=low, 2=ok.
    char topic[64], payload[8];
    makeTopic(topic, sizeof(topic), "tank");
    snprintf(payload, sizeof(payload), "%u", (unsigned)(statusCode <= 2 ? statusCode : 0));
    publishRetain(topic, payload, true);
}

void MqttManager::publishWeather(const WeatherData& wd)
{
    if (!wd.valid) return;

    char topic[64], payload[64];
    makeTopic(topic, sizeof(topic), "weather");
    snprintf(payload, sizeof(payload),
             "{\"temperature\":%.1f,\"humidity\":%.1f,\"pressure\":%.1f}",
             wd.temperature, wd.humidity, wd.pressure);
    publishRetain(topic, payload, true);
}

void MqttManager::publishSensorData(uint8_t plantIdx, const PlantSensorData& sd)
{
    if (plantIdx >= _cfg.num_plants) return;

    char topic[80], payload[256];
    snprintf(topic, sizeof(topic), "%s/sensor/%s",
             _cfg.mqtt.base_topic_flora,
             _cfg.plants[plantIdx].id);

    snprintf(payload, sizeof(payload),
             "{"
             "\"temperature\":%.1f,"
             "\"moisture\":%d,"
             "\"light\":%lu,"
             "\"conductivity\":%d,"
             "\"battery\":%d,"
             "\"rssi\":%d"
             "}",
             sd.temperature,
             sd.moisture,
             (unsigned long)sd.lux,
             sd.conductivity,
             sd.battery,
             sd.rssi);

    publishRetain(topic, payload, true);
}

void MqttManager::publishManIrrStatus(uint8_t pump0Idx, bool active)
{
    char topic[80], payload[8];
    snprintf(topic, sizeof(topic), "%s/pump%d/status",
             _cfg.mqtt.base_topic_flora, pump0Idx + 1);
    snprintf(payload, sizeof(payload), "%s", active ? "on" : "off");
    publishRetain(topic, payload, true);
}

void MqttManager::publishAutoIrrStatus(bool enabled)
{
    char topic[64];
    makeTopic(topic, sizeof(topic), "auto_irr_status");
    publishRetain(topic, enabled ? "1" : "0", true);
}

void MqttManager::publishSleepDisStatus(bool disabled)
{
    char topic[64];
    makeTopic(topic, sizeof(topic), "sleep_dis_status");
    publishRetain(topic, disabled ? "1" : "0", true);
}

void MqttManager::publishManIrrDurationStatus(uint32_t durationS)
{
    char topic[64], payload[16];
    makeTopic(topic, sizeof(topic), "man_irr_duration_status");
    snprintf(payload, sizeof(payload), "%lu", (unsigned long)durationS);
    publishRetain(topic, payload, false);
}

void MqttManager::publishAutoIrrDurationStatus(uint8_t pump0Idx, uint32_t durationS)
{
    char topic[64], payload[16];
    snprintf(topic, sizeof(topic), "%s/auto_irr_duration%u_status",
             _cfg.mqtt.base_topic_flora, (unsigned)(pump0Idx + 1));
    snprintf(payload, sizeof(payload), "%lu", (unsigned long)durationS);
    publishRetain(topic, payload, false);
}

void MqttManager::publishManIrrCmdReset()
{
    // Publish retained "0" to man_irr_cmd so the broker no longer re-delivers
    // a stale pump command on the next wakeup.
    char topic[80];
    makeTopic(topic, sizeof(topic), "man_irr_cmd");
    publishRetain(topic, "0", true, 1);
    log_i("%s: man_irr_cmd reset (retained \"0\" published)", TAG);
}

void MqttManager::publishScheduledStatus(bool scheduled)
{
    char topic[64];
    makeTopic(topic, sizeof(topic), "scheduled");
    publishRetain(topic, scheduled ? "1" : "0", true);
}

void MqttManager::publishPumpLastRun(uint8_t pump0Idx, time_t ts, uint8_t triggerCode)
{
    char topic[80];
    snprintf(topic, sizeof(topic), "%s/pump%u/last_run",
             _cfg.mqtt.base_topic_flora, (unsigned)(pump0Idx + 1));

    const char* trigger = "unknown";
    switch (triggerCode) {
        case PUMP_TRIGGER_AUTO:   trigger = "auto";    break;
        case PUMP_TRIGGER_MANUAL: trigger = "manual";  break;
        case PUMP_TRIGGER_UNKNOWN:
        default:                  trigger = "unknown"; break;
    }

    char payload[160];
    if (ts == 0) {
        snprintf(payload, sizeof(payload),
                 "{\"epoch\":0,\"iso\":\"\",\"trigger\":\"%s\"}",
                 trigger);
    } else {
        struct tm tm;
        localtime_r(&ts, &tm);
        char buf[40];
        // Use %z for numeric timezone offset (e.g. +0200). Many ISO parsers accept this.
        strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S%z", &tm);
        snprintf(payload, sizeof(payload),
                 "{\"epoch\":%lu,\"iso\":\"%s\",\"trigger\":\"%s\"}",
                 (unsigned long)ts, buf, trigger);
    }

    publishRetain(topic, payload, true);
}

// ─────────────────────────────────────────────────────────────────────────────
// Home Assistant Discovery
// ─────────────────────────────────────────────────────────────────────────────

#ifdef HA_DISCOVERY_EN
void MqttManager::publishDiscovery()
{
    // Device block shared by all entities
    char devBlock[256];
    snprintf(devBlock, sizeof(devBlock),
             "\"device\":{\"identifiers\":[\"%s\"],\"name\":\"Flora2\","
             "\"model\":\"Flora2 Arduino\",\"manufacturer\":\"matthias-bs\","
             "\"sw_version\":\"%s\"}",
             _clientId, FLORA2_VERSION);

    char topic[128], payload[512];

    // Battery voltage sensor
    snprintf(topic, sizeof(topic),
             "homeassistant/sensor/%s/ubatt/config", _clientId);
    snprintf(payload, sizeof(payload),
             "{\"name\":\"Battery\",\"unique_id\":\"%s_ubatt\","
             "\"state_topic\":\"%s/ubatt\","
             "\"unit_of_measurement\":\"mV\","
             "\"device_class\":\"voltage\",%s}",
             _clientId, _cfg.mqtt.base_topic_flora, devBlock);
    publishRetain(topic, payload, true);

    // Tank status sensor
    snprintf(topic, sizeof(topic),
             "homeassistant/sensor/%s/tank/config", _clientId);
    snprintf(payload, sizeof(payload),
             "{\"name\":\"Tank\",\"unique_id\":\"%s_tank\","
             "\"state_topic\":\"%s/tank\",%s}",
             _clientId, _cfg.mqtt.base_topic_flora, devBlock);
    publishRetain(topic, payload, true);

    // Per-plant sensors
    for (uint8_t i = 0; i < _cfg.num_plants; i++) {
        const char* id = _cfg.plants[i].id;

        const struct { const char* suffix; const char* name; const char* unit; const char* dc; } fields[] = {
            { "temperature",  "Temperature",  "°C",     "temperature" },
            { "moisture",     "Moisture",     "%",      "humidity"    },
            { "light",        "Light",        "lx",     "illuminance" },
            { "conductivity", "Conductivity", "µS/cm",  nullptr       },
            { "battery",      "Battery",      "%",      "battery"     },
        };

        for (auto& f : fields) {
            snprintf(topic, sizeof(topic),
                     "homeassistant/sensor/%s_%s/%s/config",
                     _clientId, id, f.suffix);
            char dc_part[64] = "";
            if (f.dc) snprintf(dc_part, sizeof(dc_part), "\"device_class\":\"%s\",", f.dc);
            snprintf(payload, sizeof(payload),
                     "{\"name\":\"%s %s\",\"unique_id\":\"%s_%s_%s\","
                     "\"state_topic\":\"%s/sensor/%s\","
                     "\"value_template\":\"{{ value_json.%s }}\","
                     "\"unit_of_measurement\":\"%s\",%s%s}",
                     id, f.name, _clientId, id, f.suffix,
                     _cfg.mqtt.base_topic_flora, id,
                     f.suffix,
                     f.unit, dc_part, devBlock);
            publishRetain(topic, payload, true);
        }
    }
}
#endif // HA_DISCOVERY_EN

// ─────────────────────────────────────────────────────────────────────────────
// Message callback
// ─────────────────────────────────────────────────────────────────────────────

void MqttManager::onMessage(String& topic, String& payload)
{
    log_d("%s: RX [%s] %s", TAG, topic.c_str(), payload.c_str());

    char ctrl[80];

    // man_irr_cmd
    makeTopic(ctrl, sizeof(ctrl), "man_irr_cmd");
    if (topic == ctrl) {
        int pump = payload.toInt();
        if (pump >= 1 && pump <= NUM_PUMPS) {
            pendingManIrrCmd = pump;  // store 1-based; 0 and invalid payloads are ignored
            log_i("%s: Manual irrigation cmd for pump %d", TAG, pump);
        }
        return;
    }

    // man_irr_duration_ctrl
    makeTopic(ctrl, sizeof(ctrl), "man_irr_duration_ctrl");
    if (topic == ctrl) {
        uint32_t dur = (uint32_t)payload.toInt();
        if (dur > 0 && dur <= 3600) {
            pendingManIrrDuration    = dur;
            pendingManIrrDurationSet = true;
            log_i("%s: Manual duration set to %lu s", TAG, (unsigned long)dur);
        }
        return;
    }

    // auto_irr_ctrl
    makeTopic(ctrl, sizeof(ctrl), "auto_irr_ctrl");
    if (topic == ctrl) {
        pendingAutoIrrValue = (payload == "1" || payload == "true");
        pendingAutoIrrSet   = true;
        log_i("%s: Auto irrigation %s", TAG, pendingAutoIrrValue ? "enabled" : "disabled");
        return;
    }

    // sleep_dis_ctrl
    makeTopic(ctrl, sizeof(ctrl), "sleep_dis_ctrl");
    if (topic == ctrl) {
        pendingSleepDisValue = (payload == "1" || payload == "true");
        pendingSleepDisSet   = true;
        log_i("%s: Deep sleep %s", TAG, pendingSleepDisValue ? "disabled" : "enabled");
        return;
    }

    // auto_irr_duration1_ctrl / auto_irr_duration2_ctrl
    for (uint8_t p = 0; p < NUM_PUMPS; p++) {
        char suffix[32];
        snprintf(suffix, sizeof(suffix), "auto_irr_duration%u_ctrl", (unsigned)(p + 1));
        makeTopic(ctrl, sizeof(ctrl), suffix);
        if (topic == ctrl) {
            uint32_t dur = (uint32_t)payload.toInt();
            if (dur > 0 && dur <= 3600) {
                pendingAutoIrrDuration[p]    = dur;
                pendingAutoIrrDurationSet[p] = true;
                log_i("%s: Auto duration pump%u set to %lu s", TAG, (unsigned)(p + 1), (unsigned long)dur);
            }
            return;
        }
    }

    // MQTT sensor interface: {base_topic_sensors}/{plant_id}
    if (_cfg.sensor.sensor_interface == SensorInterface::MQTT) {
        for (uint8_t i = 0; i < _cfg.num_plants; i++) {
            char sensorTopic[80];
            snprintf(sensorTopic, sizeof(sensorTopic), "%s/%s",
                     _cfg.mqtt.base_topic_sensors, _cfg.plants[i].id);
            if (topic == sensorTopic) {
                JsonDocument doc;
                if (deserializeJson(doc, payload) == DeserializationError::Ok) {
                    PlantSensorData& d = mqttSensorData[i];
                    if (!doc["temperature"].isNull())  d.temperature  = doc["temperature"].as<float>();
                    if (!doc["moisture"].isNull())     d.moisture     = (uint8_t)doc["moisture"].as<int>();
                    if (!doc["light"].isNull())        d.lux          = (uint32_t)doc["light"].as<unsigned long>();
                    else if (!doc["lux"].isNull())     d.lux          = (uint32_t)doc["lux"].as<unsigned long>();
                    if (!doc["conductivity"].isNull()) d.conductivity = (uint16_t)doc["conductivity"].as<int>();
                    if (!doc["battery"].isNull())      d.battery      = (uint8_t)doc["battery"].as<int>();
                    if (!doc["rssi"].isNull())         d.rssi         = doc["rssi"].as<int>();
                    d.last_update  = time(nullptr);
                    d.valid        = true;
                    mqttSensorUpdated[i] = true;
                    log_i("%s: MQTT sensor data for %s updated", TAG, _cfg.plants[i].id);
                }
                return;
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Private helpers
// ─────────────────────────────────────────────────────────────────────────────

bool MqttManager::publishRetain(const char* topic, const char* payload, bool retain, int qos)
{
    log_i("%s: TX topic=%s retain=%d qos=%d payload=%s",
          TAG, topic, retain ? 1 : 0, qos, payload ? payload : "");

    bool ok = _client.publish(topic, payload, retain, qos);
    if (!ok) {
        log_w("%s: Publish failed on %s (connected=%d lastError=%d returnCode=%d)",
              TAG, topic, _client.connected() ? 1 : 0,
              (int)_client.lastError(), (int)_client.returnCode());
    } else {
        log_i("%s: Publish OK on %s", TAG, topic);
    }
    return ok;
}

void MqttManager::makeTopic(char* buf, size_t len, const char* suffix) const
{
    snprintf(buf, len, "%s/%s", _cfg.mqtt.base_topic_flora, suffix);
}
