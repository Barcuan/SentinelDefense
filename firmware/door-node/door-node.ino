// Sentinel-X : programme définitif de l'ESP8266 de la porte.
//
// Carte : « NodeMCU 1.0 (ESP-12E Module) ». Bibliothèques (Outils → Gérer les bibliothèques) :
//   PubSubClient (Nick O'Leary) et DHT sensor library (Adafruit).
// Les réglages (Wi-Fi, broker, mot de passe, certificat) sont dans secrets.h,
// généré par « python -m sentinel.setup » sur le PC serveur. Ne jamais le commiter.
//
// Ce que fait l'ESP :
//   reçoit  sentinel/door/led    green | red | idle   → LED verte / rouge / éteintes
//   reçoit  sentinel/door/fire   numéro du tir        → un aller-retour du servo (numéro déjà vu = ignoré)
//   envoie  sentinel/door/climate  {"temp":..,"hum":..,"gas":..} toutes les 2 s
//   envoie  sentinel/door/status   online, et offline automatiquement si l'ESP disparaît
// Lien perdu depuis plus de 2 s → LED éteintes ; sans lien, aucun ordre de tir ne peut arriver.

#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Servo.h>
#include <DHT.h>
#include "secrets.h"

const int LED_ROUGE = D0;
const int LED_VERTE = D8;
const int DHT_PIN = D1;
const int SERVO_PIN = D2;   // jamais D4 : impulsions au démarrage

const int REPOS = 0;        // angle du servo au repos, à régler selon l'arbalète
const int TIR = 90;         // angle qui déclenche le tir
const unsigned long TIR_MS = 500;
const unsigned long MESURE_MS = 2000;
const unsigned long LIEN_PERDU_MS = 2000;
const unsigned long RECONNEXION_MS = 3000;

const char* T_LED = "sentinel/door/led";
const char* T_FIRE = "sentinel/door/fire";
const char* T_CLIMATE = "sentinel/door/climate";
const char* T_STATUS = "sentinel/door/status";

BearSSL::WiFiClientSecure net;
BearSSL::X509List ca(CA_CERT);
PubSubClient mqtt(net);
DHT dht(DHT_PIN, DHT11);
Servo servo;

unsigned long derniereMesure = 0;
unsigned long dernierEssai = 0;
unsigned long lienPerduDepuis = 0;  // 0 = lien en place
long dernierTir = 0;

void appliquerLed(const String& etat) {
  digitalWrite(LED_VERTE, etat == "green" ? HIGH : LOW);
  digitalWrite(LED_ROUGE, etat == "red" ? HIGH : LOW);
}

void tirer() {
  Serial.println("TIR");
  servo.write(TIR);
  delay(TIR_MS);
  servo.write(REPOS);
}

void messageRecu(char* topic, byte* payload, unsigned int length) {
  String message;
  message.reserve(length);
  for (unsigned int i = 0; i < length; i++) message += (char)payload[i];

  if (strcmp(topic, T_LED) == 0) {
    appliquerLed(message);
  } else if (strcmp(topic, T_FIRE) == 0) {
    long id = message.toInt();
    if (id > 0 && id != dernierTir) {
      dernierTir = id;
      tirer();
    }
  }
}

bool connecterMqtt() {
  String clientId = "sentinel-door-" + String(ESP.getChipId(), HEX);
  Serial.printf("Connexion chiffrée au broker %s:%d… ", MQTT_HOST, MQTT_PORT);
  if (mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD, T_STATUS, 1, true, "offline")) {
    mqtt.publish(T_STATUS, "online", true);
    mqtt.subscribe(T_LED, 1);
    mqtt.subscribe(T_FIRE, 1);
    Serial.println("OK");
    return true;
  }
  char erreur[96];
  net.getLastSSLError(erreur, sizeof(erreur));
  Serial.printf("refusée (MQTT %d, TLS : %s)\n", mqtt.state(), erreur);
  return false;
}

void publierMesures() {
  float temperature = dht.readTemperature();
  float humidite = dht.readHumidity();
  int gaz = analogRead(A0);
  char json[96];
  if (isnan(temperature) || isnan(humidite)) {
    snprintf(json, sizeof(json), "{\"gas\":%d}", gaz);  // lecture DHT ratée : on n'envoie pas de fausse valeur
  } else {
    snprintf(json, sizeof(json), "{\"temp\":%.1f,\"hum\":%.0f,\"gas\":%d}", temperature, humidite, gaz);
  }
  mqtt.publish(T_CLIMATE, json);
}

void setup() {
  servo.attach(SERVO_PIN, 500, 2400);  // plage d'impulsions du SG90
  servo.write(REPOS);                  // au repos avant tout le reste
  pinMode(LED_ROUGE, OUTPUT);
  pinMode(LED_VERTE, OUTPUT);
  appliquerLed("idle");

  Serial.begin(115200);
  Serial.println();
  Serial.println("Sentinel-X : démarrage");
  dht.begin();

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Wi-Fi « %s »", WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.printf(" OK, adresse %s\n", WiFi.localIP().toString().c_str());

  net.setTrustAnchors(&ca);
  net.setX509Time(CERT_TIME);  // valide le certificat du broker sans Internet
  if (net.probeMaxFragmentLength(MQTT_HOST, MQTT_PORT, 1024)) {
    net.setBufferSizes(1024, 1024);  // moins de mémoire si le broker l'accepte
  }
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(messageRecu);
  mqtt.setKeepAlive(3);  // le PC voit « hors ligne » en ~5 s si l'ESP disparaît
}

void loop() {
  if (!mqtt.connected()) {
    if (lienPerduDepuis == 0) lienPerduDepuis = millis();
    if (millis() - lienPerduDepuis > LIEN_PERDU_MS) appliquerLed("idle");
    if (millis() - dernierEssai >= RECONNEXION_MS) {
      dernierEssai = millis();
      if (WiFi.status() == WL_CONNECTED && connecterMqtt()) lienPerduDepuis = 0;
    }
    return;
  }
  mqtt.loop();
  if (millis() - derniereMesure >= MESURE_MS) {
    derniereMesure = millis();
    publierMesures();
  }
}
