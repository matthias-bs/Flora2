///////////////////////////////////////////////////////////////////////////////
// Flora2Arduino.ino
//
// Flora2 — Automated plant irrigation system for ESP32
//
// Ports 09_software/_main.py (MicroPython) to Arduino/C++.
//
// Hardware (GPIO assignments in Flora2Cfg.h):
//   • Capacitive moisture sensors  ADC1 (GPIO 34/35/32/33)
//   • DS18B20 OneWire temperature  GPIO 5
//   • I2C weather sensor           SDA=26, SCL=25
//   • Pump control                 GPIO 19, 18
//   • Tank level sensors           GPIO 23 (low), 21 (empty)
//   • Sensor power rail            GPIO 27
//   • Battery voltage ADC          GPIO 35
//   • MiFlora BLE sensors          (direct GATT read via NimBLE)
// Note: On default Flora2 PCB, moisture sensor 2 and battery ADC are both on GPIO 35.
// Re-routing either signal to a different GPIO requires a hardware patch on the PCB.
//
// Required libraries:
//   NimBLE-Arduino          (h2zero)
//   ArduinoJson             (bblanchon)
//   arduino-mqtt            (256dpi)
//   OneWireNg               (pstolarz)     — when TEMPERATURE_SENSOR_EN defined
//   pocketBME280            (angrest)      — when WEATHER_SENSOR_BME280 defined
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include <Arduino.h>
#include <esp_sleep.h>
#include <esp_efuse.h>
#include <Preferences.h>
#include <Wire.h>

#include "Flora2Cfg.h"
#include "secrets.h"
#include "src/ConfigLoader.h"
#include "src/Tank.h"
#include "src/Pump.h"
#include "src/MoistureSensor.h"
#include "src/DS1820.h"
#include "src/WeatherSensor.h"
#include "src/MiFloraSensor.h"
#include "src/Irrigation.h"
#include "src/WiFiManager.h"
#include "src/MqttManager.h"

// ─── RTC state (survives deep sleep, cleared on power-off) ───────────────────

RTC_DATA_ATTR static time_t  rtc_pump_last_run[NUM_PUMPS]   = { 0, 0 };
RTC_DATA_ATTR static bool    rtc_auto_irr_enabled            = DEF_AUTO_IRRIGATION;
RTC_DATA_ATTR static bool    rtc_sleep_disabled              = false;
RTC_DATA_ATTR static uint32_t rtc_man_irr_duration           = DEF_IRR_DURATION_MAN;
RTC_DATA_ATTR static uint32_t rtc_cycle_count                = 0;
RTC_DATA_ATTR static bool    rtc_first_boot                  = true;
// Last man_irr_cmd value (1-based pump number) that was handled this power-on session.
// Guards against re-firing if the broker reset publish fails and the retained
// message is re-delivered on the next wakeup with the same value.
RTC_DATA_ATTR static uint8_t  rtc_last_man_irr_cmd            = 0;  ///< 0 = none
// Auto irrigation duration per pump (s) — MQTT-overridable, 0 = use config.json value.
RTC_DATA_ATTR static uint32_t rtc_auto_irr_duration[NUM_PUMPS] = { 0, 0 };
// Last trigger source per pump for last_run payload: 0=unknown, 1=auto, 2=manual.
RTC_DATA_ATTR static uint8_t rtc_pump_last_trigger[NUM_PUMPS] = {
    PUMP_TRIGGER_UNKNOWN,
    PUMP_TRIGGER_UNKNOWN
};

// ─── Global objects ───────────────────────────────────────────────────────────

static AppConfig      gCfg;
static Tank           gTank(PIN_TANK_LOW, PIN_TANK_EMPTY);
static Pump           gPumps[NUM_PUMPS] = { Pump(PIN_PUMP_1, 0), Pump(PIN_PUMP_2, 1) };
static MoistureSensor gMoisture;
static DS1820         gDS1820(PIN_ONEWIRE);
static WeatherSensor  gWeather;
static MiFloraSensor  gMiFlora;
static WiFiMgr        gWiFi;

// MqttManager and Irrigation are created after config is loaded
static MqttManager*   gpMqtt       = nullptr;
static Irrigation*    gpIrrigation = nullptr;

// Plant sensor data (filled by BLE / local ADC / MQTT each cycle)
static PlantSensorData gSensorData[MAX_PLANT_SENSORS];

// ─── Helpers ─────────────────────────────────────────────────────────────────

static uint32_t measureBatteryMv()
{
#ifdef BATTERY_VOLTAGE_EN
    uint32_t sum = 0;
    for (int i = 0; i < UBATT_SAMPLES; i++) {
        sum += analogReadMilliVolts(PIN_UBATT_ADC);
        delay(5);
    }
    return (uint32_t)((float)(sum / UBATT_SAMPLES) * UBATT_DIV_FACTOR);
#else
    return 0;
#endif
}

/// Collect BLE MAC addresses from plant config into a vector.
static std::vector<std::string> buildBleAddressList()
{
    std::vector<std::string> addrs;
    for (uint8_t i = 0; i < gCfg.num_plants; i++) {
        addrs.push_back(std::string(gCfg.plants[i].address));
    }
    return addrs;
}

/// Populate gSensorData from local moisture ADC (LOCAL mode).
static void readLocalSensors()
{
    for (uint8_t i = 0; i < gCfg.num_plants; i++) {
        int pin = gCfg.plants[i].adc_pin;
        if (pin < 0) continue;
        float pct = gMoisture.getMoisture(pin);
        if (pct < 0.0f) continue;
        gSensorData[i].moisture    = (uint8_t)pct;
        gSensorData[i].valid       = true;
        gSensorData[i].last_update = time(nullptr);
        log_i("Plant[%d] moisture (local ADC): %d%%", i, gSensorData[i].moisture);
    }
}

/// Copy sensor data received via MQTT into gSensorData.
static void syncMqttSensorData()
{
    for (uint8_t i = 0; i < gCfg.num_plants; i++) {
        if (gpMqtt->mqttSensorUpdated[i]) {
            gSensorData[i] = gpMqtt->mqttSensorData[i];
            gpMqtt->mqttSensorUpdated[i] = false;
        }
    }
}

/// Enter deep sleep or busy-wait depending on config and battery state.
static void goToSleep(uint32_t battery_mV)
{
    uint32_t period = (battery_mV > 2000 && battery_mV < gCfg.general.battery_weak)
                      ? gCfg.general.processing_period2
                      : gCfg.general.processing_period;

    if (gCfg.general.deep_sleep && !rtc_sleep_disabled) {
        log_i("Deep sleeping for %lu s", (unsigned long)period);
        esp_sleep_enable_timer_wakeup((uint64_t)period * 1000000ULL);
        esp_deep_sleep_start();
        // Does not return
    } else {
        log_i("Waiting %lu s (deep sleep disabled)", (unsigned long)period);
        uint32_t ms = period * 1000UL;
        uint32_t start = millis();
        while ((millis() - start) < ms) {
            if (gpMqtt && gpMqtt->isConnected()) gpMqtt->loop();
            delay(500);
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// setup()
// ─────────────────────────────────────────────────────────────────────────────

void setup()
{
    Serial.begin(115200);
    delay(500);
    // Ensure timezone environment is set on every boot so localtime()/getLocalTime()
    // return the correct local time after deep-sleep resets (TZ is not retained).
    setenv("TZ", TIMEZONE_STR, 1);
    tzset();
    log_i("Flora2 Arduino v%s — boot #%lu", FLORA2_VERSION, (unsigned long)rtc_cycle_count);

    // Sensor power rail on before I2C/OneWire init
    pinMode(PIN_SENSOR_POWER, OUTPUT);
    digitalWrite(PIN_SENSOR_POWER, HIGH);
    delay(100);  // Allow sensors to stabilise

    // Load runtime configuration from LittleFS
    ConfigLoader::load(gCfg);

    // Create objects that depend on config
    gpMqtt = new MqttManager(gCfg);
    gpIrrigation = new Irrigation([&]() {
        if (gpMqtt && gpMqtt->isConnected()) gpMqtt->loop();
    });

    // Hardware init
    gTank.begin();
    for (uint8_t i = 0; i < NUM_PUMPS; i++) gPumps[i].begin();

#ifdef TEMPERATURE_SENSOR_EN
    if (!gDS1820.begin()) {
        log_w("DS1820: no devices found");
    }
#endif

    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    if (gCfg.sensor.weather_sensor) {
        if (!gWeather.begin()) {
            log_w("Weather sensor init failed");
        }
    }

    // Battery check — force extended sleep if critically low
    uint32_t battMv = measureBatteryMv();
    if (battMv > 2000 && battMv < gCfg.general.battery_low) {
        log_e("Battery critically low (%lu mV) — deep sleeping 1 h", (unsigned long)battMv);
        esp_sleep_enable_timer_wakeup(3600ULL * 1000000ULL);
        esp_deep_sleep_start();
    }

    // Initialise sensor data array timestamps
    if (rtc_first_boot) {
        memset(gSensorData, 0, sizeof(gSensorData));
        // Seed RTC auto-duration from compiled-in defaults on first power-on.
        // These will be overridden by config.json values below, and later by MQTT.
        rtc_auto_irr_duration[0] = DEF_IRR_DURATION_AUTO1;
        rtc_auto_irr_duration[1] = DEF_IRR_DURATION_AUTO2;
        rtc_first_boot = false;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// loop()
// ─────────────────────────────────────────────────────────────────────────────

void loop()
{
    uint32_t battMv = measureBatteryMv();
    log_i("Battery: %lu mV", (unsigned long)battMv);

    // ── 1. Sensor power on, allow warm-up ────────────────────────────────────
    digitalWrite(PIN_SENSOR_POWER, HIGH);
    delay(200);

    // ── 2. Read weather sensor ────────────────────────────────────────────────
    WeatherData weatherData = {};
    if (gCfg.sensor.weather_sensor) {
        if (!gWeather.isReady()) {
            // Sensor rail may be enabled only during loop(); retry init after power-on.
            if (!gWeather.begin()) {
                log_w("Weather sensor re-init failed");
            }
        }
        if (gWeather.read()) {
            weatherData = gWeather.data();
        }
    }

    // ── 3. Read ambient temperature (DS1820) ──────────────────────────────────
#ifdef TEMPERATURE_SENSOR_EN
    gDS1820.requestAll();
    ambientTemp = gDS1820.getTemperatureC(0);
    log_i("Ambient: %.2f°C", ambientTemp);
#endif

    // ── 4. Read plant sensor data ─────────────────────────────────────────────
    if (gCfg.sensor.sensor_interface == SensorInterface::BLE) {
        auto addrs = buildBleAddressList();

        gMiFlora.readBattery(addrs, gSensorData, gCfg.num_plants);

        uint8_t complete = 0;
        for (uint8_t i = 0; i < gCfg.num_plants; i++) {
            if (gSensorData[i].valid_mask != 0) complete++;
        }
        log_i("BLE direct GATT: %d/%d sensors complete", complete, gCfg.num_plants);
    } else if (gCfg.sensor.sensor_interface == SensorInterface::LOCAL) {
        readLocalSensors();
    }
    // MQTT mode: sensor data collected during the MQTT session below

    // ── 5. WiFi + MQTT ────────────────────────────────────────────────────────
    bool wifiOk = gWiFi.connect();
    if (wifiOk && rtc_cycle_count == 0) {
        // First boot: sync NTP
        gWiFi.ntpSync(TIMEZONE_STR, NTP_SERVER_1, NTP_SERVER_2, NTP_SERVER_3);
    } else if (wifiOk) {
        // Re-sync periodically (every 12 h ≈ every 48 cycles at 15-min period)
        if (rtc_cycle_count % 48 == 0) {
            gWiFi.ntpSync(TIMEZONE_STR, NTP_SERVER_1, NTP_SERVER_2, NTP_SERVER_3);
        }
    }

    if (wifiOk && gpMqtt->connect()) {
#ifdef HA_DISCOVERY_EN
        // Publish discovery once on first boot
        if (rtc_cycle_count == 0) gpMqtt->publishDiscovery();
#endif

        // Let incoming messages arrive (especially MQTT sensor mode)
        for (int i = 0; i < 10; i++) {
            gpMqtt->loop();
            delay(200);
        }

        // In MQTT sensor mode, copy received data to gSensorData
        if (gCfg.sensor.sensor_interface == SensorInterface::MQTT) {
            syncMqttSensorData();
        }

        // Apply any pending control commands from MQTT
        if (gpMqtt->pendingAutoIrrSet) {
            rtc_auto_irr_enabled            = gpMqtt->pendingAutoIrrValue;
            // Propagate to live config for this cycle
            gCfg.general.auto_irrigation    = rtc_auto_irr_enabled;
            gpMqtt->pendingAutoIrrSet        = false;
            gpMqtt->publishAutoIrrStatus(rtc_auto_irr_enabled);
        }
        if (gpMqtt->pendingSleepDisSet) {
            rtc_sleep_disabled          = gpMqtt->pendingSleepDisValue;
            gpMqtt->pendingSleepDisSet  = false;
            gpMqtt->publishSleepDisStatus(rtc_sleep_disabled);
        }
        if (gpMqtt->pendingManIrrDurationSet) {
            rtc_man_irr_duration               = gpMqtt->pendingManIrrDuration;
            gpMqtt->pendingManIrrDurationSet   = false;
        }
        for (uint8_t p = 0; p < NUM_PUMPS; p++) {
            if (gpMqtt->pendingAutoIrrDurationSet[p]) {
                rtc_auto_irr_duration[p]            = gpMqtt->pendingAutoIrrDuration[p];
                gpMqtt->pendingAutoIrrDurationSet[p] = false;
            }
        }

        // Some brokers or network conditions can drop the session shortly after
        // CONNECT/subscribe. Re-check before publishing state payloads.
        if (!gpMqtt->isConnected()) {
            log_w("MQTT disconnected before publish block - reconnecting");
            if (gpMqtt->connect()) {
                gpMqtt->loop();
                delay(50);
            } else {
                log_e("MQTT reconnect failed - skipping publish block this cycle");
            }
        }

        // ── 6. Publish sensor data ────────────────────────────────────────────
        if (gpMqtt->isConnected()) {
            log_i("MQTT publish block: start");
            gpMqtt->publishBattery(battMv);
            TankStatus tankStatus = gTank.read();
            uint8_t tankCode = (tankStatus == TankStatus::EMPTY) ? 0 :
                       (tankStatus == TankStatus::TANK_LOW) ? 1 : 2;
            gpMqtt->publishTank(tankCode);

            if (weatherData.valid) gpMqtt->publishWeather(weatherData);

            for (uint8_t i = 0; i < gCfg.num_plants; i++) {
                bool publishPlant = gSensorData[i].valid;
                if (gCfg.sensor.sensor_interface == SensorInterface::BLE) {
                    publishPlant = (gSensorData[i].valid_mask != 0);
                }
                if (publishPlant) {
                    gpMqtt->publishSensorData(i, gSensorData[i]);
                }
            }
            log_i("MQTT publish block: done");
        } else {
            log_w("MQTT publish block skipped: disconnected");
        }

        // ── 7. Manual irrigation (triggered by MQTT command) ─────────────────
        // pendingManIrrCmd holds the 1-based pump number from the retained
        // man_irr_cmd topic, or -1 if no message arrived this cycle.
        // We only fire if the received value differs from the last one we handled
        // (rtc_last_man_irr_cmd), preventing re-fires on every wakeup.
        // After running, we publish a retained "0" to reset the broker's stored
        // value so subsequent wakeups see no pending command.
        if (gpMqtt->pendingManIrrCmd >= 1) {
            uint8_t receivedCmd = (uint8_t)gpMqtt->pendingManIrrCmd;
            gpMqtt->pendingManIrrCmd = -1;

            if (receivedCmd != rtc_last_man_irr_cmd) {
                uint8_t pIdx = receivedCmd - 1;  // convert to 0-based
                if (pIdx < NUM_PUMPS) {
                    // Guard: record what we're about to handle before running
                    // so a crash mid-run still prevents a spurious re-fire.
                    rtc_last_man_irr_cmd = receivedCmd;
                    gpMqtt->publishManIrrStatus(pIdx, true);
                    PumpResult manualRes = gpIrrigation->manualIrrigate(
                        pIdx,
                        rtc_man_irr_duration,
                        gPumps[pIdx],
                        gTank,
                        rtc_pump_last_run[pIdx]
                    );
                    if (manualRes != PumpResult::TANK_EMPTY) {
                        rtc_pump_last_trigger[pIdx] = PUMP_TRIGGER_MANUAL;
                    }
                    gpMqtt->publishManIrrStatus(pIdx, false);
                    gpMqtt->publishPumpLastRun(
                        pIdx,
                        rtc_pump_last_run[pIdx],
                        rtc_pump_last_trigger[pIdx]
                    );
                    gpMqtt->loop();
                    // Reset broker's retained value → next wakeup sees "0", no re-fire.
                    gpMqtt->publishManIrrCmdReset();
                    rtc_last_man_irr_cmd = 0;
                }
            } else {
                log_i("man_irr_cmd %d: duplicate of last handled — ignoring", receivedCmd);
            }
        }

        // ── 8. Auto irrigation ────────────────────────────────────────────────
        // Apply runtime auto-duration overrides from MQTT (0 = use config.json default).
        for (uint8_t p = 0; p < NUM_PUMPS; p++) {
            if (rtc_auto_irr_duration[p] > 0) {
                gCfg.general.irr_duration_auto[p] = rtc_auto_irr_duration[p];
            }
        }

        IrrigationDecision decisions[NUM_PUMPS];
        gpIrrigation->autoIrrigate(gCfg,
                                    gSensorData,
                                    gPumps,
                                    NUM_PUMPS,
                                    gTank,
                                    rtc_pump_last_run,
                                    decisions);

        // Report results
        bool anyScheduled = false;
        for (uint8_t p = 0; p < NUM_PUMPS; p++) {
            if (decisions[p].ran) {
                gpMqtt->publishManIrrStatus(p, false);  // pump finished
                gpMqtt->loop();
                if (decisions[p].result != PumpResult::TANK_EMPTY) {
                    rtc_pump_last_trigger[p] = PUMP_TRIGGER_AUTO;
                }
            }
            if (decisions[p].scheduled) anyScheduled = true;
        }

        // Publish the retained current pump state every cycle so subscribers
        // always see "off" plus the last known run timestamp even if no pump ran.
        for (uint8_t p = 0; p < NUM_PUMPS; p++) {
            gpMqtt->publishManIrrStatus(p, false);
            gpMqtt->publishPumpLastRun(p, rtc_pump_last_run[p], rtc_pump_last_trigger[p]);
            gpMqtt->publishAutoIrrDurationStatus(p, gCfg.general.irr_duration_auto[p]);
        }
        gpMqtt->publishAutoIrrStatus(gCfg.general.auto_irrigation);
        gpMqtt->publishSleepDisStatus(rtc_sleep_disabled);
        gpMqtt->publishManIrrDurationStatus(rtc_man_irr_duration);
        gpMqtt->publishScheduledStatus(anyScheduled);

        // Final loop flush before disconnect
        gpMqtt->loop();
        gpMqtt->disconnect();
    }

    gWiFi.disconnect();

    // ── 9. Sensor power off ───────────────────────────────────────────────────
    digitalWrite(PIN_SENSOR_POWER, LOW);

    rtc_cycle_count++;
    log_i("Cycle %lu complete", (unsigned long)rtc_cycle_count);

    // ── 10. Sleep ─────────────────────────────────────────────────────────────
    goToSleep(battMv);
}
