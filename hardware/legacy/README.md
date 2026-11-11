# Legacy / alternative firmware (superseded)

These sketches used the **old JSON-over-serial** protocol and the separate
`serial_bridge.py` relay. They are kept for reference only.

**Use instead:** `hardware/esp32_threat_siren/` (ESP32) — the current pipe-protocol
firmware that works with the built-in server bridge (`app/hardware.py`) and with
the updated optional `serial_bridge.py`. The ESP32 DevKit sketch is also provided,
identical, at `hardware/esp32_devkit_threat_siren/` for the "devkit" name.

- `esp32_threat_siren.ino` / `esp32_devkit_threat_siren.ino` — loose copies of
  earlier sketches (the canonical versions now live in their own sketch folders).
- `nodemcu_threat_siren.ino` — ESP8266/NodeMCU variant (JSON protocol).
- `esp32_standalone_wifi_honeypot.ino` — separate standalone Wi-Fi experiment.

To use the NodeMCU/ESP8266 with the current server, flash the ESP32 sketch logic
adapted for your pins, or drive it via the updated `serial_bridge.py`.
