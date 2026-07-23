# ESP32 Firmware Architecture Specification

**Status:** Locked System Architecture  
**Target Board:** ESP32-C3 Microcontroller (RISC-V Single-Core @ 160 MHz)  
**RTOS Environment:** ESP-IDF v5.x / FreeRTOS  
**BLE Stack:** NimBLE  
**Date:** July 23, 2026  

---

## 1. Executive Summary & Design Principles

This document defines the production software architecture for ESP32-C3 firmware operating Vikzar **Universal Pods** and **EMG Bands**. 

### Firmware Design Principles:
1. **Zero Dynamic Allocation in Hot Path:** All FreeRTOS queues, buffers, and packet structures are statically allocated at startup to eliminate heap fragmentation and memory leaks.
2. **Interrupt-Driven Sampling:** Sensor sampling occurs inside timed hardware timer interrupts (ISR) at 100 Hz, ensuring zero jitter.
3. **Task Isolation:** Sensor acquisition, packet formatting, BLE transmission, and power management run as isolated FreeRTOS tasks with strict priority ordering.
4. **Fail-Safe Operation:** Hardware watchdogs monitor task health; invalid sensor states or BLE stack lockups trigger safe restarts without data corruption.

---

## 2. Layered Architecture Overview

```
+-------------------------------------------------------------------------------+
|                             APPLICATION LAYER                                 |
|  - System State Machine (BOOT, IDLE, CONNECTED, RECORDING, SLEEP, ERROR)      |
|  - Command Processor (Time Sync, Start/Stop Capture, Deep Sleep)              |
|  - Session Context & Sequence Counter Management                              |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                           PACKET BUILDER MODULE                               |
|  - Encapsulates sensor readings into VDPP v1.0 binary structures              |
|  - Calculates CRC-16/CCITT-FALSE over Header + Payload                        |
|  - Manages VDPP Header status flags & 64-bit device millisecond timestamp     |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                            BLE NETWORK LAYER (NimBLE)                         |
|  - NimBLE GATT Server Task & GAP Connection Handler                           |
|  - VSDS Stream & Command Characteristic Handlers                              |
|  - RingBuffer Queue for 100 Hz Notification Delivery                           |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                           HARDWARE DRIVER LAYER                               |
|  - IMU Driver: SPI/I2C DMA driver for 6-axis IMU (Accel/Gyro @ 100 Hz)        |
|  - FSR Driver: ESP32 ADC1 DMA driver for 3x Force-Sensitive Resistors          |
|  - EMG Driver: ESP32 ADC1 DMA driver for Dual-Channel Muscle Biopotentials    |
|  - Power Driver: ADC Voltage Divider & Li-Po Charging Status GPIO             |
+-------------------------------------------------------------------------------+
```

---

## 3. FreeRTOS Task & Queue Topology

| Task Name | Priority | Core | Stack Size | Period / Trigger | Description |
|---|---|---|---|---|---|
| `Task_SensorSample` | 5 (Highest) | Core 0 | 4096 B | 100 Hz (10 ms ISR) | Reads IMU via SPI DMA & FSR/EMG via ADC1 DMA. Pushes `RawSample` struct to `xSensorQueue`. |
| `Task_PacketEncoder`| 4 (High) | Core 0 | 4096 B | Queue Triggered | Pops `RawSample`, formats VDPP v1.0 packet, computes CRC-16, pushes byte array to `xBLETxQueue`. |
| `Task_BLEService` | 3 (Medium) | Core 0 | 6144 B | Event Driven | NimBLE event task. Pops `xBLETxQueue` and emits BLE GATT notification on Characteristic `7B9E0002`. |
| `Task_CommandProcessor`| 2 (Low-Med) | Core 0 | 3072 B | Event Driven | Processes incoming `COMMAND_REQ` (Time Sync, Start/Stop) and emits `COMMAND_ACK`. |
| `Task_TelemetryPower` | 1 (Lowest) | Core 0 | 3072 B | 5000 ms (5 s) | Measures battery voltage/temperature, updates VDPP `HEARTBEAT` characteristic `7B9E0011`. |

### Inter-Task Queues (Statically Allocated):
- **`xSensorQueue`**: Depth 10 `RawSample` structs (holds up to 100ms of buffered sensor data during transient BLE latency).
- **`xBLETxQueue`**: Depth 10 VDPP packet byte arrays (`uint8_t[41]`).

---

## 4. Hardware Pinout & Peripherals Mapping

### ESP32-C3 Microcontroller Hardware Allocations:

```
                  +-------------------------------+
                  |          ESP32-C3             |
                  |                               |
  IMU SPI SCK  <--| GPIO4                 GPIO0   |--> FSR 1 / Quadriceps (ADC1_CH0)
  IMU SPI MOSI <--| GPIO6                 GPIO1   |--> FSR 2 / Hamstrings (ADC1_CH1)
  IMU SPI MISO -->| GPIO5                 GPIO2   |--> FSR 3 / EMG Ref    (ADC1_CH2)
  IMU SPI CS   <--| GPIO7                 GPIO3   |--> Battery Voltage    (ADC1_CH3)
  IMU INT1     -->| GPIO8                 GPIO10  |--> Charging Detect    (Input Pullup)
                  +-------------------------------+
```

> **ADC Safety Rule:** All analog inputs (FSRs, EMG, Battery Voltage) use **ADC1 only** (GPIO0–GPIO3). **ADC2 is never used** because ADC2 is shared with the Wi-Fi/BLE radio and would produce noisy/corrupted readings during BLE transmission.

---

## 5. System State Machine

```
               +-------------------+
               |     POWER ON      |
               +---------+---------+
                         |
                         v
               +-------------------+
               |  SYSTEM_INIT      | (Peripherals, FreeRTOS Queues, NimBLE Stack)
               +---------+---------+
                         |
                         v
               +-------------------+
               |   ADVERTISING     | <-----------------------+
               +---------+---------+                         |
                         | BLE Connect                       | BLE Disconnect
                         v                                   |
               +-------------------+                         |
               |    CONNECTED      | ------------------------+
               +---------+---------+
                         | START_CAPTURE Command
                         v
               +-------------------+
               |    RECORDING      | (100 Hz Sensor Sample & VDPP Stream Active)
               +---------+---------+
                         | STOP_CAPTURE / Sleep Command
                         v
               +-------------------+
               |    DEEP_SLEEP     | (ULP RTC wakeup or Power Switch toggle)
               +-------------------+
```

---

## 6. Power Management Architecture

1. **Active Streaming Mode:** ESP32-C3 CPU runs at 160 MHz. BLE modem uses automatic light sleep between connection events. Expected current draw: ~15–25 mA.
2. **Idle Connected Mode:** 80 MHz CPU frequency. Expected current draw: ~5–8 mA.
3. **Deep Sleep Mode:** RTC timer or GPIO interrupt wake up. Sensors powered down via high-side MOSFET power gate. Expected current draw: < 10 µA.
4. **Low Battery Handling:** When battery drops below 3.3V (approx 5% SOC), firmware emits final `HEARTBEAT` with Low Battery status flag set, closes BLE connection, and enters deep sleep to prevent battery over-discharge.
