# SmartFit Socket Kit: Development of a Low-Cost Smart Socket Fitting System for Transtibial Prosthesis

## Overview

The **SmartFit Socket Kit** is a low-cost smart socket fitting system designed to improve the fitting process for transtibial (below-knee) prostheses. The system combines pressure sensing, embedded systems, Bluetooth communication, and a mobile application to provide real-time feedback for prosthetic socket fitting.

Designed specifically for low-resource settings, the project helps technicians achieve better socket alignment and pressure distribution, reducing discomfort, pressure sores, and prosthesis abandonment.

---

## Problem Statement

Many transtibial prosthesis users experience pain, pressure sores, and poor mobility due to improper socket fitting. In many developing countries, access to trained prosthetists and advanced fitting equipment is limited.

The SmartFit Socket Kit addresses this challenge by providing an affordable, portable, and offline solution that assists technicians during the socket fitting process.

---

## Features

- Real-time pressure monitoring
- 12 Force Sensing Resistor (FSR) sensors
- ESP32 microcontroller
- Bluetooth Low Energy (BLE) communication
- Android mobile application
- Color-coded pressure heatmap
- Fit Quality Score (0–100)
- Voice-guided fitting instructions
- Offline functionality
- CSV data export
- Lightweight and portable design

---

## Hardware Components

- ESP32-WROOM-32 Development Board
- 12 × Interlink 402 FSR Sensors
- Medical-grade silicone liner
- TP4056 Battery Charging Module
- 3000mAh 18650 Battery
- Voltage Divider Circuit
- Capacitors
- Zener Diodes
- 3D Printed Protective Case

---

## Software Technologies

- Flutter
- Bluetooth Low Energy (BLE)
- TensorFlow Lite
- Hive Database
- Arduino IDE
- ESP32 Firmware

---

## System Workflow

1. Pressure sensors detect socket interface pressure.
2. ESP32 collects sensor readings.
3. Data is transmitted via Bluetooth.
4. Android application processes the data.
5. Pressure heatmap is generated.
6. Fit Quality Score is calculated.
7. Voice and visual recommendations are provided.
8. Technician adjusts the socket.
9. Process repeats until an optimal fit is achieved.

---

## Mathematical Model

The SmartFit system calculates:

- Pressure distribution
- Pressure deviation ratio
- Hotspot detection
- Fit Quality Score (FQS)

These algorithms help identify pressure hotspots and recommend corrective adjustments.

---

## Project Objectives

- Develop a low-cost pressure sensing system.
- Improve prosthetic socket fitting accuracy.
- Reduce pressure-related injuries.
- Provide offline guidance for technicians.
- Increase prosthesis comfort and usability.

---

## Applications

- Prosthetics and Orthotics Clinics
- Rehabilitation Centers
- Biomedical Engineering Research
- Rural Healthcare Facilities
- Educational Demonstrations

---

## Technologies Used

- Biomedical Engineering
- Embedded Systems
- Internet of Things (IoT)
- Mobile Application Development
- Bluetooth Communication
- Sensor Technology
- Signal Processing

---

## Future Improvements

- Machine Learning-based fitting recommendations
- Cloud synchronization
- Patient history management
- Remote monitoring
- AI-assisted prosthetic fitting
- Integration with additional biomedical sensors

---

## Repository Structure

```
SmartFit-Socket-Kit/
│
├── Hardware/
├── Firmware/
├── Mobile-App/
├── Circuit-Diagrams/
├── Documentation/
├── Images/
├── Results/
├── References/
└── README.md
```

---

## Getting Started

### Prerequisites

- Arduino IDE
- Flutter SDK
- Android Studio
- Proteus (optional)
- ESP32 Board Package

### Installation

1. Clone the repository.

```bash
git clone https://github.com/your-username/transtibial-prosthesis.git
```

2. Open the firmware in Arduino IDE.

3. Upload the code to the ESP32.

4. Open the Flutter project.

5. Run the Android application.

6. Connect to the ESP32 via Bluetooth.

---

## Expected Results

- Accurate pressure distribution monitoring
- Real-time pressure heatmap
- Fit Quality Score between 0–100
- Reduced pressure hotspots
- Improved prosthetic comfort
- Faster socket fitting process
