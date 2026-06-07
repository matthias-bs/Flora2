///////////////////////////////////////////////////////////////////////////////
// src/WiFiManager.cpp
//
// MIT License — Copyright (c) 2026 Matthias Prinke
///////////////////////////////////////////////////////////////////////////////

#include "WiFiManager.h"
#include "../secrets.h"
#include "../Flora2Cfg.h"

#if defined(CORE_DEBUG_LEVEL) && (CORE_DEBUG_LEVEL > 0)
static const char* TAG = "WiFiMgr";
#endif

// Maximum time to wait for NTP sync after connect (seconds).
static constexpr uint32_t NTP_TIMEOUT_S = 30;

bool WiFiMgr::connect()
{
    WiFi.mode(WIFI_STA);

    for (uint8_t n = 0; n < NUM_WIFI_NETWORKS; n++) {
        const char* ssid = WIFI_NETWORKS[n].ssid;
        const char* pass = WIFI_NETWORKS[n].password;
        log_i("%s: Trying SSID \"%s\"", TAG, ssid);
        WiFi.begin(ssid, pass);

        uint8_t attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < MAX_WIFI_RETRIES) {
            delay(500);
            attempts++;
        }

        if (WiFi.status() == WL_CONNECTED) {
            log_i("%s: Connected, IP=%s", TAG, WiFi.localIP().toString().c_str());
            return true;
        }

        WiFi.disconnect(true);
        log_w("%s: SSID \"%s\" failed", TAG, ssid);
    }

    log_e("%s: All networks failed", TAG);
    return false;
}

bool WiFiMgr::ntpSync(const char* tzInfo,
                       const char* server1,
                       const char* server2,
                       const char* server3)
{
    if (!isConnected()) {
        log_e("%s: Not connected — cannot sync NTP", TAG);
        return false;
    }

    // configTzTime sets timezone and starts SNTP
    const char* s2 = (server2 && *server2) ? server2 : nullptr;
    const char* s3 = (server3 && *server3) ? server3 : nullptr;
    configTzTime(tzInfo, server1, s2, s3);

    log_i("%s: Waiting for NTP sync...", TAG);
    uint32_t start = millis();
    struct tm timeinfo;
    while (!getLocalTime(&timeinfo)) {
        if ((millis() - start) > NTP_TIMEOUT_S * 1000UL) {
            log_e("%s: NTP sync timed out", TAG);
            return false;
        }
        delay(500);
    }

    char buf[64];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S %Z", &timeinfo);
    log_i("%s: Time synced: %s", TAG, buf);
    return true;
}

void WiFiMgr::disconnect()
{
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    log_i("%s: Disconnected", TAG);
}

bool WiFiMgr::isConnected() const
{
    return WiFi.status() == WL_CONNECTED;
}
