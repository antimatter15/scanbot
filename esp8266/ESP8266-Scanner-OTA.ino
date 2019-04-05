#include <ESP8266WiFi.h>
#include <ESP8266mDNS.h>
#include <WiFiUdp.h>
#include <ArduinoOTA.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h>


#ifndef STASSID
#define STASSID "YOUR SSID HERE"
#define STAPSK  "YOUR WIFI PASSWORD HERE"
#endif

const char* ota_password = "OTA PROGRAMMING PASSWORD";
const char* host = "scanbot";
const char* SERVER_HOSTNAME = "compooter.local";


const int LID_PIN = 16;

ESP8266WebServer httpServer(80);

unsigned long last_time;
int state;
int last_state;

int scan_count = 0;
String printer_address = "N/A";


void handleRoot() {
  int n = MDNS.queryService("http", "tcp");

  String response;

  if (digitalRead(LID_PIN)) {
    response += "LID IS OPEN";
  } else {
    response += "LID IS CLOSED";
  }

  response += "\n\n";

  response += "Printer Address: " + printer_address + "\n";
  response += "Uptime: " + TimeToString(millis()) + "\n";
  response += "Scan Count (since last power cycle): " + String(scan_count) + "\n\n";
  

  for (int i = 0; i < n; ++i) {
    response +=  MDNS.hostname(i) + ": " + String(MDNS.IP(i)[0]) + String(".") + \
                 String(MDNS.IP(i)[1]) + String(".") + \
                 String(MDNS.IP(i)[2]) + String(".") + \
                 String(MDNS.IP(i)[3]) + "\n";
  }

  httpServer.send(200, "text/plain", response);


}


void setup() {
  pinMode(16, INPUT);

  Serial.begin(115200);
  Serial.println("Booting");
  WiFi.mode(WIFI_STA);
  WiFi.begin(STASSID, STAPSK);
  while (WiFi.waitForConnectResult() != WL_CONNECTED) {
    Serial.println("Connection Failed! Rebooting...");
    delay(5000);
    ESP.restart();
  }

  // Port defaults to 8266
  // ArduinoOTA.setPort(8266);

  // Hostname defaults to esp8266-[ChipID]
  ArduinoOTA.setHostname(host);
  ArduinoOTA.setPassword(ota_password);

  ArduinoOTA.onStart([]() {
    String type;
    if (ArduinoOTA.getCommand() == U_FLASH) {
      type = "sketch";
    } else { // U_SPIFFS
      type = "filesystem";
    }

    // NOTE: if updating SPIFFS this would be the place to unmount SPIFFS using SPIFFS.end()
    Serial.println("Start updating " + type);
  });
  ArduinoOTA.onEnd([]() {
    Serial.println("\nEnd");
  });
  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("Progress: %u%%\r", (progress / (total / 100)));
  });
  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("Error[%u]: ", error);
    if (error == OTA_AUTH_ERROR) {
      Serial.println("Auth Failed");
    } else if (error == OTA_BEGIN_ERROR) {
      Serial.println("Begin Failed");
    } else if (error == OTA_CONNECT_ERROR) {
      Serial.println("Connect Failed");
    } else if (error == OTA_RECEIVE_ERROR) {
      Serial.println("Receive Failed");
    } else if (error == OTA_END_ERROR) {
      Serial.println("End Failed");
    }
  });
  ArduinoOTA.begin();
  Serial.println("Ready");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  MDNS.begin(host);
  httpServer.on("/", handleRoot);
  httpServer.begin();
  MDNS.addService("http", "tcp", 80);
  Serial.printf("Open http://%s.local/ in your browser\n", host);  

  findServer();
}

void findServer() {
  int n = MDNS.queryService("http", "tcp");
  if (n == 0) {
    Serial.println("no services found");
  } else {
    for (int i = 0; i < n; ++i) {
      // Going through every available service,
      // we're searching for the one whose hostname
      // matches what we want, and then get its IP
      if (MDNS.hostname(i) == SERVER_HOSTNAME) {
        printer_address = String(MDNS.IP(i)[0]) + String(".") + \
                          String(MDNS.IP(i)[1]) + String(".") + \
                          String(MDNS.IP(i)[2]) + String(".") + \
                          String(MDNS.IP(i)[3]);
      }
    }
  }
}

String TimeToString(unsigned long t){
  t /= 1000;
  int days = t / 86400;
  int h = (t % 86400) / 3600;
  t = t % 3600;
  int m = t / 60;
  return String(days) + " days, " + String(h) + " hours, " + String(m) + " minutes";
}

void triggerScan() {
  findServer();
  scan_count++;
  WiFiClient client;
  HTTPClient http;

  if (http.begin(client, "http://" + printer_address + "/cgi-bin/scan")) {  // HTTP
    Serial.print("[HTTP] POST...\n");
    int httpCode = http.POST("Scan please");
    if (httpCode > 0) {
      Serial.printf("[HTTP] GET... code: %d\n", httpCode);
      if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_MOVED_PERMANENTLY) {
        String payload = http.getString();
        Serial.println(payload);
      }
    } else {
      Serial.printf("[HTTP] POST... failed, error: %s\n", http.errorToString(httpCode).c_str());
    }
    http.end();
  } else {
    Serial.printf("[HTTP] Unable to connect\n");
  }
}

void loop() {
  ArduinoOTA.handle();
  httpServer.handleClient();
  MDNS.update();


  int reading = digitalRead(LID_PIN);
  if(reading != last_state){
    last_time = millis();
  }

  if((millis() - last_time) > 300){
    if(reading != state){
      state = reading;

      if(state == 0){
        triggerScan();
      }
    }
  }
  last_state = reading;
}