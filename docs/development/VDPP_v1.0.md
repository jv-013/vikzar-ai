# Vikzar Device Data Protocol (VDPP) v1.0 Specification

**Status:** Locked Production Wire Protocol Specification  
**Version:** 1.0  
**Date:** July 23, 2026  
**Author:** Lead Hardware & Firmware Architect  

---

## 1. Overview & Purpose

The **Vikzar Device Data Protocol (VDPP v1.0)** is the official, production-locked binary wire protocol used for all wireless communication over Bluetooth Low Energy (BLE) between Vikzar wearable hardware (**Universal Pods** and **EMG Bands**) and the **Laptop ETL Pipeline**.

VDPP v1.0 replaces and supersedes the development placeholder protocol (VDPP v0.1). It provides a compact, deterministic, high-throughput binary structure optimized for 100 Hz multi-sensor streaming, hardware time synchronization, battery telemetry, device laterality, and robust CRC integrity verification.

---

## 2. Protocol Design Rules

1. **Byte Order:** Little-Endian for all multi-byte fields (`uint16`, `int16`, `uint32`, `uint64`).
2. **Fixed Framing:** Every VDPP v1.0 packet consists of a **20-byte Header**, a **Variable-Length Payload** ($L$ bytes), and a **2-byte CRC Trailer**.
3. **Deterministic Memory Alignment:** No dynamic field packing or variable-length string encoding inside high-frequency stream packets.
4. **Data Integrity:** Every packet must be validated via CRC-16/CCITT-FALSE before processing. Corrupted packets are rejected immediately.
5. **No Loss Silent Repair:** Unrecognized versions, bad CRC values, or length mismatches result in immediate packet drops and increment the telemetry error counters.

---

## 3. Complete Packet Layout

```
+-----------------------------------------------------------------------+
|                        HEADER (20 Bytes)                              |
|  0..1   : Magic Bytes (0x56, 0x44 -> "VD")                           |
|  2      : Protocol Version (0x01 -> v1.0)                             |
|  3      : Packet Type (0x01: SENSOR_DATA, 0x02: HEARTBEAT, etc.)      |
|  4      : Device Identifier (0x01: POD_LEFT, 0x02: POD_RIGHT, etc.)    |
|  5      : Mount Location (0x01: SHIN_GUARD, 0x02: SLEEVE, etc.)        |
|  6      : Status Flags (Bitmask: Low Battery, Charging, Sync, etc.)   |
|  7      : Reserved / Alignment Byte (0x00)                            |
|  8..11  : Sequence Number (uint32)                                    |
|  12..19 : Device Timestamp ms (uint64)                                |
|  20..21 : Payload Length L (uint16)                                   |
+-----------------------------------------------------------------------+
|                        PAYLOAD (L Bytes)                              |
|  Smart Pod: 18 Bytes | EMG Band: 6 Bytes | Heartbeat: 4 Bytes | ...    |
+-----------------------------------------------------------------------+
|                        TRAILER (2 Bytes)                              |
|  22+L..23+L : CRC-16/CCITT-FALSE (uint16)                             |
+-----------------------------------------------------------------------+
```

---

## 4. Header Field Specifications (20 Bytes)

| Offset | Field Name | Type | Size | Description / Valid Values |
|---|---|---|---|---|
| 0–1 | `magic` | `uint8[2]` | 2 B | Magic envelope bytes: `0x56`, `0x44` (ASCII `"VD"`). |
| 2 | `version` | `uint8` | 1 B | Protocol major version: `0x01` (VDPP v1.0). |
| 3 | `packet_type` | `uint8` | 1 B | Packet payload type:<br>`0x01`: `SENSOR_DATA`<br>`0x02`: `HEARTBEAT`<br>`0x03`: `DEVICE_INFO`<br>`0x04`: `COMMAND_REQ`<br>`0x05`: `COMMAND_ACK` |
| 4 | `device_identifier` | `uint8` | 1 B | Logical device identity & laterality:<br>`0x01`: `SMART_POD_LEFT`<br>`0x02`: `SMART_POD_RIGHT`<br>`0x03`: `EMG_BAND_LEFT`<br>`0x04`: `EMG_BAND_RIGHT` |
| 5 | `mount_location` | `uint8` | 1 B | Physical placement on athlete:<br>`0x00`: `UNSPECIFIED`<br>`0x01`: `SHIN_GUARD`<br>`0x02`: `COMPRESSION_SLEEVE`<br>`0x03`: `THIGH_BAND`<br>`0x04`: `COMPRESSION_SHORTS` |
| 6 | `status_flags` | `uint8` | 1 B | Device status bitmask:<br>**Bit 0**: Low Battery Warning (< 15%)<br>**Bit 1**: Charging Active (1 = Charging, 0 = Discharging)<br>**Bit 2**: Hardware Sensor Fault<br>**Bit 3**: Time Synchronized (1 = Sync, 0 = Unsync)<br>**Bit 4**: Active Recording Session (1 = Recording, 0 = Idle)<br>**Bits 5–7**: Reserved (0) |
| 7 | `reserved` | `uint8` | 1 B | Reserved for structure alignment; must be set to `0x00`. |
| 8–11 | `sequence_number` | `uint32` | 4 B | Monotonically increasing packet counter per device session. |
| 12–19 | `device_timestamp_ms`| `uint64` | 8 B | Hardware millisecond timestamp (ESP32 epoch/uptime clock). |
| 20–21 | `payload_length` | `uint16` | 2 B | Length $L$ of the payload section in bytes. |

---

## 5. Payload Specifications

### 5.1 Packet Type `0x01` — `SENSOR_DATA`

#### A. Smart Pod Payload ($L = 18$ Bytes)
Struct format: `<hhhhhhHHH` (Little-Endian)

| Field Name | Type | Size | Range / Scale | Description |
|---|---|---|---|---|
| `accel_x` | `int16` | 2 B | $\pm 16\text{g}$ ($1\text{ LSB} = 0.000488\text{g}$) | Linear Acceleration X |
| `accel_y` | `int16` | 2 B | $\pm 16\text{g}$ ($1\text{ LSB} = 0.000488\text{g}$) | Linear Acceleration Y |
| `accel_z` | `int16` | 2 B | $\pm 16\text{g}$ ($1\text{ LSB} = 0.000488\text{g}$) | Linear Acceleration Z |
| `gyro_x` | `int16` | 2 B | $\pm 2000^\circ/\text{s}$ ($1\text{ LSB} = 0.061^\circ/\text{s}$) | Angular Velocity X |
| `gyro_y` | `int16` | 2 B | $\pm 2000^\circ/\text{s}$ ($1\text{ LSB} = 0.061^\circ/\text{s}$) | Angular Velocity Y |
| `gyro_z` | `int16` | 2 B | $\pm 2000^\circ/\text{s}$ ($1\text{ LSB} = 0.061^\circ/\text{s}$) | Angular Velocity Z |
| `fsr_1` | `uint16` | 2 B | 0–4095 (12-bit ADC) | Heel / Primary FSR Force |
| `fsr_2` | `uint16` | 2 B | 0–4095 (12-bit ADC) | Midfoot FSR Force |
| `fsr_3` | `uint16` | 2 B | 0–4095 (12-bit ADC) | Forefoot FSR Force |

#### B. EMG Band Payload ($L = 6$ Bytes)
Struct format: `<HHH` (Little-Endian)

| Field Name | Type | Size | Range / Scale | Description |
|---|---|---|---|---|
| `quadriceps` | `uint16` | 2 B | 0–4095 (12-bit ADC) | Quadriceps EMG Biopotential Envelope |
| `hamstring` | `uint16` | 2 B | 0–4095 (12-bit ADC) | Hamstring EMG Biopotential Envelope |
| `raw_emg_ref` | `uint16` | 2 B | 0–4095 (12-bit ADC) | Reference Electrode Baseline Noise |

---

### 5.2 Packet Type `0x02` — `HEARTBEAT` ($L = 4$ Bytes)
Emitted periodically (default: every 5 seconds) or when battery level changes.  
Struct format: `<BHb` (Little-Endian)

| Field Name | Type | Size | Description |
|---|---|---|---|
| `battery_percentage` | `uint8` | 1 B | State of Charge (0–100%). |
| `battery_millivolts` | `uint16` | 2 B | Battery terminal voltage in millivolts (e.g. 3720 = 3.72V). |
| `board_temperature_c` | `int8` | 1 B | ESP32 internal die temperature in °C. |

---

### 5.3 Packet Type `0x03` — `DEVICE_INFO` ($L = 32$ Bytes)
Emitted on BLE connection establishment or upon `COMMAND_REQ` query.  
Struct format: `<BBBBH16s6s4x` (Little-Endian)

| Field Name | Type | Size | Description |
|---|---|---|---|
| `fw_major` | `uint8` | 1 B | Firmware Major Version |
| `fw_minor` | `uint8` | 1 B | Firmware Minor Version |
| `fw_patch` | `uint8` | 1 B | Firmware Patch Version |
| `fw_build` | `uint8` | 1 B | Firmware Build Number |
| `hardware_revision` | `uint16` | 2 B | Hardware PCB revision code (e.g. `0x0100` = v1.0) |
| `serial_number` | `char[16]` | 16 B | Device Serial Number (ASCII null-padded) |
| `mac_address` | `uint8[6]` | 6 B | Hardware BLE MAC Address |
| `reserved` | `uint8[4]` | 4 B | Reserved for alignment/future build info |

---

### 5.4 Packet Type `0x04` — `COMMAND_REQ` & `0x05` — `COMMAND_ACK`

Used for Time Synchronization, Capture Control, and Sleep Management over the Command Characteristic.

#### Command Identifiers (`command_id` - uint8):
- `0x01`: `TIME_SYNC_REQUEST`  
  - *Payload ($L = 8$ B):* `laptop_timestamp_ms` (`uint64`). Laptop sends its current epoch timestamp.
- `0x02`: `TIME_SYNC_RESPONSE`  
  - *Payload ($L = 24$ B):* `laptop_timestamp_ms` (`uint64`), `device_rx_timestamp_ms` (`uint64`), `device_tx_timestamp_ms` (`uint64`). Device calculates clock offset $\Delta t$.
- `0x03`: `START_CAPTURE`  
  - *Payload ($L = 4$ B):* `session_id_hash` (`uint32`). Device sets `status_flags` Bit 4 to 1 and resets sequence counter.
- `0x04`: `STOP_CAPTURE`  
  - *Payload ($L = 0$ B):* Device sets `status_flags` Bit 4 to 0.
- `0x05`: `ENTER_DEEP_SLEEP`  
  - *Payload ($L = 0$ B):* Device disables sensors and enters ESP32 deep sleep mode.

---

## 6. Trailer Specification (2 Bytes)

| Field Name | Type | Size | Description |
|---|---|---|---|
| `crc16` | `uint16` | 2 B | CRC-16/CCITT-FALSE checksum calculated across all bytes from `magic` (Byte 0) up to the final payload byte (Byte $21+L$). Polynomial `0x1021`, Initial value `0xFFFF`. |

---

## 7. Protocol Extensibility & Compatibility Rules

1. **Header Stability:** The 22-byte envelope (20-byte Header + 2-byte Trailer) is fixed for all 1.x protocol versions.
2. **Unknown Packet Types:** Decoders encountering an unknown `packet_type` (> `0x05`) must parse `payload_length`, skip $L$ bytes, verify CRC, and safely ignore the payload without crashing.
3. **Backward Compatibility:** Future 1.x revisions may append fields to existing payloads by increasing `payload_length`. Decoders must verify `payload_length >= expected_min_length` to remain backward-compatible.
