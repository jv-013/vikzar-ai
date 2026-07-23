# Production BLE GATT Specification

**Status:** Locked Architecture Specification  
**Version:** 1.0  
**Date:** July 23, 2026  
**Target:** ESP32-C3 Firmware & Laptop Ingestion Pipeline (`bleak`)  

---

## 1. Overview & GATT Profile Hierarchy

The Vikzar BLE GATT Architecture defines the primary wireless interface between physical wearable hardware (Universal Pods and EMG Bands) and the **Laptop Ingestion Pipeline**.

All Vikzar custom services share a dedicated 128-bit UUID base: `7B9E0000-6F34-4B2B-A1A8-8F0E4D2C0000`.

```
Vikzar Peripheral (ESP32-C3 GATT Server)
 ├── Generic Access Service (0x1800)
 ├── Generic Attribute Service (0x1801)
 ├── Device Information Service (0x180A)
 ├── Battery Service (0x180F)
 ├── Vikzar Sensor Data Service (VSDS) (7B9E0001-...)
 │    ├── Stream Characteristic (NOTIFY) [7B9E0002-...]
 │    └── Command & Sync Characteristic (WRITE, INDICATE) [7B9E0003-...]
 └── Vikzar Telemetry Service (VDTS) (7B9E0010-...)
      ├── Heartbeat Characteristic (READ, NOTIFY) [7B9E0011-...]
      └── Device Metadata Characteristic (READ) [7B9E0012-...]
```

---

## 2. Service & Characteristic Definitions

### 2.1 Vikzar Sensor Data Service (VSDS)
**Service UUID:** `7B9E0001-6F34-4B2B-A1A8-8F0E4D2C0000`

#### A. Stream Characteristic
- **UUID:** `7B9E0002-6F34-4B2B-A1A8-8F0E4D2C0000`
- **Properties:** `NOTIFY`
- **Max Payload / MTU:** 247 Bytes negotiated (att_mtu = 247). Packets fit comfortably within a single BLE PDU without fragmentation.
- **Description:** Emits high-frequency VDPP v1.0 `SENSOR_DATA` (Packet Type `0x01`) packets at 100 Hz (every 10ms).

#### B. Command & Sync Characteristic
- **UUID:** `7B9E0003-6F34-4B2B-A1A8-8F0E4D2C0000`
- **Properties:** `WRITE`, `INDICATE`
- **Description:** Laptop writes `COMMAND_REQ` (Packet Type `0x04`) packets (Time Sync, Start Capture, Stop Capture, Deep Sleep). Device responds with `COMMAND_ACK` (Packet Type `0x05`) via `INDICATE`.

---

### 2.2 Vikzar Telemetry Service (VDTS)
**Service UUID:** `7B9E0010-6F34-4B2B-A1A8-8F0E4D2C0000`

#### A. Heartbeat Characteristic
- **UUID:** `7B9E0011-6F34-4B2B-A1A8-8F0E4D2C0000`
- **Properties:** `READ`, `NOTIFY`
- **Description:** Emits VDPP v1.0 `HEARTBEAT` (Packet Type `0x02`) packets every 5 seconds. Contains state-of-charge percentage, voltage in mV, and board temperature.

#### B. Device Metadata Characteristic
- **UUID:** `7B9E0012-6F34-4B2B-A1A8-8F0E4D2C0000`
- **Properties:** `READ`
- **Description:** Exposes VDPP v1.0 `DEVICE_INFO` (Packet Type `0x03`) packet (Firmware major/minor/patch/build, hardware revision, serial number, BLE MAC address).

---

### 2.3 Standard BLE Services

#### A. Device Information Service (DIS - `0x180A`)
- **Manufacturer Name (`0x2A29`):** `"Vikzar Inc."`
- **Model Number (`0x2A24`):** `"Universal Pod v1"` / `"EMG Band v1"`
- **Firmware Revision (`0x2A26`):** E.g. `"1.0.0+42"`

#### B. Battery Service (BAS - `0x180F`)
- **Battery Level (`0x2A19`):** `READ`, `NOTIFY` — uint8 percentage (0–100%).

---

## 3. BLE Connection & Advertising Protocol

### 3.1 Advertising Data Structure
ESP32-C3 advertises continuously when disconnected or idle.

- **Advertising Flags:** `0x06` (LE General Discoverable Mode, BR/EDR Not Supported).
- **Service UUIDs (16-bit / 128-bit):** Advertises VSDS (`7B9E0001-...`).
- **Complete Local Name:**
  - `VKZ-POD-L-XXXX` (Smart Pod Left)
  - `VKZ-POD-R-XXXX` (Smart Pod Right)
  - `VKZ-EMG-L-XXXX` (EMG Band Left)
  - `VKZ-EMG-R-XXXX` (EMG Band Right)
  *(where `XXXX` is the last 4 characters of the device MAC address)*

### 3.2 Connection Parameters & Reconnection Policy
- **Connection Interval:** 7.5 ms – 15 ms (Fast connection for 100 Hz low-latency streaming).
- **Slave Latency:** 0
- **Supervision Timeout:** 2000 ms (2 seconds).
- **MTU Negotiation:** ESP32 requests MTU exchange immediately on connect (Target: 247 Bytes).
- **Reconnection Policy:** `BleakBLETransport` retries up to 3 times with exponential backoff (`1s`, `2s`, `4s`). On unexpected disconnect, NimBLE fires GATT disconnect callback and resumes advertising within 50ms.

---

## 4. Hardware Time Synchronization Handshake

To ensure sample-accurate alignment across multi-device streams without relying on phone/laptop BLE arrival latency:

```
Laptop (BLE Central)                                ESP32 (BLE Peripheral)
        |                                                     |
        |--- WRITE Command (TIME_SYNC_REQUEST, T_laptop_tx) ->|
        |                                                     | Record T_esp_rx
        |                                                     | Process Sync
        |                                                     | Record T_esp_tx
        |<- INDICATE Command (TIME_SYNC_RESPONSE, ------------|
        |    T_laptop_tx, T_esp_rx, T_esp_tx)                 |
        v                                                     v
Calculates Round-Trip Delay (RTT) & Clock Offset:
RTT = (T_laptop_rx - T_laptop_tx) - (T_esp_tx - T_esp_rx)
Clock Offset Δt = T_esp_rx - (T_laptop_tx + RTT / 2)
```

The Laptop stores $\Delta t$ per connected device and converts every `device_timestamp_ms` to unified Laptop Master Time prior to ETL synchronization.
