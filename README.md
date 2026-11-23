# Object and Human Sensing Using Wi-Fi

## Project Overview

Object and Human Sensing Using Wi-Fi is an ESP32-based sensing project that explores the use of Wi-Fi Channel State Information (CSI) to detect human presence and movement within an environment.

Instead of relying on cameras or conventional motion sensors, the system analyzes changes in Wi-Fi signal characteristics caused by movement and interactions within the environment.

The project provides real-time visualization of wireless signal variations through thermal heatmaps and live graphs, allowing users to monitor motion activity without direct visual observation.

## Project Objectives

- Explore Wi-Fi CSI technology for wireless sensing.
- Detect human presence using changes in Wi-Fi signals.
- Identify movement through variations in CSI data.
- Process and analyze wireless signal characteristics in real time.
- Visualize signal variations through interactive graphs and thermal heatmaps.
- Demonstrate a camera-free approach to human motion detection.

## How It Works

The system operates through four main stages:

1. **Transmit:** A Wi-Fi router continuously sends wireless packets through the environment.
2. **Reflect:** Wi-Fi signals interact with surrounding objects and people, causing changes in signal propagation.
3. **Receive:** The ESP32 records Channel State Information (CSI) from incoming Wi-Fi packets.
4. **Analyze:** The collected CSI data is processed to identify signal variations associated with human presence and movement.

### Signal Processing

The collected CSI data goes through several processing stages:

- **Data Collection:** Receive CSI measurements from the ESP32.
- **Filtering:** Reduce noise and smooth signal variations.
- **Feature Extraction:** Measure changes in signal characteristics.
- **Motion Detection:** Apply a threshold to identify potential human activity.

## Hardware Components

- **ESP32 Development Board:** Collects wireless signal data for sensing.
- **Wi-Fi Router:** Transmits wireless signals through the environment.
- **USB Cable:** Provides power and connects the ESP32 to the computer.
- **Laptop:** Processes and visualizes the collected data.

## Software & Technologies

- **Python:** Core programming and signal processing.
- **Flask:** Hosts the local web dashboard.
- **NumPy:** Numerical processing and data analysis.
- **PySerial:** Serial communication with the ESP32.
- **Real-Time Data Visualization:** Live graphs and thermal heatmaps.

## Project Features

### 1. Real-Time CSI Line Graph

Displays live CSI Energy and RSSI measurements, alongside a Motion Index and dynamic threshold for monitoring human movement.

### 2. Real-Time Thermal Heatmap

Visualizes CSI signal variations through color intensity, representing changes in motion activity. It also supports adjustable sensitivity and switching between raw signal and motion visualization.

### 3. Localhost Web Dashboard

A browser-based dashboard hosted locally using Flask at:

`http://127.0.0.1:5000`

It provides:
- Real-time thermal heatmap.
- Human motion intensity visualization.
- Motion detection status.
- Packet rate monitoring.
- RSSI monitoring.
- Adjustable detection sensitivity.
- Raw signal visualization.

## Project Structure

```text
Object-sensing-by-Wi-Fi/
│
├── csi_core.py
├── csi_heatmap.py
├── csi_line.py
├── csi_web.py
├── README.md
└── Object & human sensing by wi-fi (1).pdf
```

- `csi_core.py`: Core processing and Wi-Fi CSI data analysis.
- `csi_line.py`: Real-time CSI signal monitoring and motion detection.
- `csi_heatmap.py`: Thermal heatmap and motion visualization.
- `csi_web.py`: Localhost web dashboard.

## Project Presentation

[View the Project Presentation (PDF)](./Object%20%26%20human%20sensing%20by%20wi-fi%20%281%29.pdf)

## Project Status

The project has a working prototype featuring ESP32-based CSI data collection, real-time signal processing, motion detection, and visualization through live graphs and a local web dashboard.

Further development and testing will focus on improving detection reliability and expanding the system's capabilities.

## Team Members

- Raghad Alzayyat
- Hagar Elkholy
- Mohaned Ekramy
- Pola Fady

**Project Supervisor:** Dr. Tamer Medhat

## Future Work

- Explore object detection using Wi-Fi signal variations.
- Improve human presence and movement detection accuracy.
- Test the system under different environmental conditions.
- Enhance signal processing and noise reduction.
- Investigate additional Wi-Fi sensing applications.

---

**Project:** Object and Human Sensing Using Wi-Fi  
**Category:** Wireless Sensing / Wi-Fi CSI / Human Motion Detection
