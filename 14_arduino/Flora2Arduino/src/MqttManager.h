///////////////////////////////////////////////////////////////////////////////
// src/MqttManager.h
//
// MQTT connection, publish and subscribe manager.
//
// Uses 256dpi/arduino-mqtt (MQTTClient).
//
// Subscribed control topics (all under cfg.mqtt.base_topic_flora):
//   man_irr_cmd             payload: "1" or "2" (1-based pump number)
//   man_irr_duration_ctrl   payload: seconds as decimal string
//   auto_irr_ctrl           payload: "0" or "1"
//   sleep_dis_ctrl          payload: "0" or "1"
// Published plant sensor state topics:
//   {base_topic_flora}/sensor/{plant.id}
//
// When sensor_interface == MQTT, also subscribes to:
//   {base_topic_sensors}/{plant.id}  payload: JSON with temperature/moisture/
//                                             conductivity/light/battery fields
//
// Pending state changes are exposed as public fields.  The main sketch reads
// them after each loop() call and commits them to RTC_DATA_ATTR variables.
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#pragma once
#include <Arduino.h>
#include <MQTT.h>
#include "../Flora2Cfg.h"
#ifdef MQTT_TLS_EN
  #include <NetworkClientSecure.h>
#else
  #include <WiFiClient.h>
#endif
#include "ConfigLoader.h"

// Shared trigger source codes for pump last_run payloads.
enum PumpTrigger : uint8_t {
    PUMP_TRIGGER_UNKNOWN = 0,
    PUMP_TRIGGER_AUTO    = 1,
    PUMP_TRIGGER_MANUAL  = 2
};

class MqttManager {
public:
    explicit MqttManager(const AppConfig& cfg);

    /// Connect to broker with LWT, then subscribe to control topics.
    /// @return true on success
    bool connect();

    void disconnect();

    /// Process incoming messages — call frequently.
    bool loop();

    bool isConnected();

    // ── Publish helpers ──────────────────────────────────────────────────────
    void publishStatus(const char* status, bool retain = true);
    void publishBattery(uint32_t voltage_mV);
    void publishTank(uint8_t statusCode);
    void publishWeather(const WeatherData& wd);
    void publishSensorData(uint8_t plantIdx, const PlantSensorData& sd);
    void publishManIrrStatus(uint8_t pump0Idx, bool active);
    void publishAutoIrrStatus(bool enabled);
    void publishSleepDisStatus(bool disabled);
    void publishManIrrDurationStatus(uint32_t durationS);
    void publishAutoIrrDurationStatus(uint8_t pump0Idx, uint32_t durationS);
    void publishScheduledStatus(bool scheduled);
    void publishPumpLastRun(uint8_t pump0Idx, time_t ts, uint8_t triggerCode);
    /// Publish retained "0" to man_irr_cmd, clearing the broker's stored command.
    void publishManIrrCmdReset();

#ifdef HA_DISCOVERY_EN
    void publishDiscovery();
#endif

    // ── Pending state changes (set by message callback) ───────────────────────
    int      pendingManIrrCmd;           ///< -1 = none, 1/2 = 1-based pump number
    bool     pendingManIrrDurationSet;
    uint32_t pendingManIrrDuration;      ///< seconds
    bool     pendingAutoIrrSet;
    bool     pendingAutoIrrValue;
    bool     pendingAutoIrrDurationSet[NUM_PUMPS];
    uint32_t pendingAutoIrrDuration[NUM_PUMPS];  ///< seconds, per pump
    bool     pendingSleepDisSet;
    bool     pendingSleepDisValue;

    /// MQTT mode: populated by incoming sensor topic messages.
    PlantSensorData mqttSensorData[MAX_PLANT_SENSORS];
    bool            mqttSensorUpdated[MAX_PLANT_SENSORS];

private:
    const AppConfig&    _cfg;

#ifdef MQTT_TLS_EN
    NetworkClientSecure _net;
#else
    WiFiClient          _net;
#endif
    MQTTClient          _client;

    char _clientId[32];

    void onMessage(String& topic, String& payload);
    bool publishRetain(const char* topic, const char* payload, bool retain = false, int qos = 0);

    // Build full topic: {base_topic_flora}/{suffix}
    void makeTopic(char* buf, size_t len, const char* suffix) const;
};
