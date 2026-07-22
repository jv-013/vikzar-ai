# Sensor Specifications

## Purpose

This document defines the wearable sensors used by Vikzar AI and the information captured from each sensor.

---

# Overview

Vikzar AI uses two wearable systems.

1. Smart Shin Pad
2. EMG Band (Training Only)

Together they provide biomechanical and physiological information required for AI training.

---

# Smart Shin Pad

The Smart Shin Pad is the primary wearable device.

It is worn during:

- Training
- Matches

Sensors include

- IMU
- FSR

---

# IMU

Measures

- Linear Acceleration
- Angular Velocity

Axes

- X
- Y
- Z

Provides

- Running Mechanics
- Jump Dynamics
- Landing Characteristics
- Direction Changes
- Rotational Movement
- Impact Detection

---

# FSR

Measures

Ground Contact Force

Applications

- Foot Strike
- Landing
- Push-off
- Balance
- Weight Transfer
- Contact Timing

---

# EMG Band

Used only during training.

Measures electrical muscle activity.

Muscles monitored include

- Quadriceps
- Hamstrings

Additional muscles may be supported depending on hardware.

---

# Training Mode

Player wears

Smart Shin Pad

+

EMG Band

The ETL synchronizes both sensor systems.

---

# Match Mode

Player wears

Smart Shin Pad only.

The AI estimates muscle activity using relationships learned during training.

---

# Sampling

Target

100 Hz

---

# Design Principles

Sensors should

- Produce reliable measurements
- Be synchronized
- Support real-time processing
- Remain hardware independent from AI