# Noise_Level_Sensor-System
The Noise Level Sensor System will measure the Real time Sound Pressure Levels in dB and perform the Acoustic Analysis by Calculating the SPL Metrics Like Leq, L10,L50 and L90 and 1/3 Octave Band Frequency Analysis.The Noise Level Data is Published on Home Assistant via MQTT Broker Setup

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MQTT](https://img.shields.io/badge/MQTT-Enabled-orange.svg)](https://mqtt.org/)

A comprehensive real-time noise monitoring system with frequency analysis, event detection, and Home Assistant integration.

##  Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [MQTT Topics](#mqtt-topics)
- [Home Assistant Integration](#home-assistant-integration)
- [Calibration](#calibration)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

##  Features

- **Real-time SPL Monitoring**: Continuous sound pressure level measurement with EMA filtering
- **Noise Event Detection**: Automatic detection of noise events above configurable threshold
- **Frequency Analysis**: 1/3 Octave band analysis with L10/L50/L90 statistical levels
- **Audio Clip Recording**: Saves 5-second audio clips when noise events occur
- **Data Visualization**: Automatic generation of frequency analysis plots
- **MQTT Integration**: Real-time data publishing with Home Assistant auto-discovery
- **Location Tracking**: GPS coordinates publishing for device positioning
- **Hourly Statistics**: Automated hourly noise level summaries
- **Status Monitoring**: System health and connectivity monitoring

##  System Architecture

`
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Microphone    │───▶│  Audio Buffer   │───▶│   SPL Analysis  │
│   (44.1kHz)     │    │   (0.5s)        │    │   (EMA Filter)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌─────────────────┐               ▼
│ Event Detection │◀───│   Threshold     │    ┌─────────────────┐
│   (86dB)        │    │   Monitor       │    │   MQTT Broker   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                                             │
         ▼                                             ▼
┌─────────────────┐                         ┌─────────────────┐
│ Audio Clip Save │                         │ Home Assistant  │
│   (5s .wav)     │                         │   Dashboard     │
└─────────────────┘                         └─────────────────┘
         │
         ▼
┌─────────────────┐
│ Frequency       │
│ Analysis & Plot │
│   (.png)        │
└─────────────────┘
`

##  Hardware Requirements

### Audio Input
- **Microphone**: USB or built-in microphone (recommended: external USB mic)
- **Interface**: Compatible with system audio drivers
- **Sample Rate**: 44.1kHz minimum

### System Requirements
- **OS**: Linux/Windows/macOS
- **RAM**: 512MB minimum, 1GB recommended
- **Storage**: 1GB for clips/plots (depends on event frequency)
- **Network**: Ethernet/WiFi for MQTT connectivity

##  Software Requirements

- **Python**: 3.8 - 3.11
- **Dependencies**: Listed in 
equirements_noisecheck.txt

##  Installation

### Step 1: Clone the Repository
git clone https://github.com/yourusername/noise-level-detection.git
cd noise-level-detection
`

### Step 2: Create Virtual Environment
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/macOS
python -m venv .venv
source .venv/bin/activate
`

### Step 3: Install Dependencies

pip install -r requirements.txt
`

### Step 4: Verify Audio Setup

# List available audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"
`

## ⚙️ Configuration

### Basic Configuration (
oise_monitor_updated.py)

Edit the following variables in the script:

`python
# Device identification
NODE_ID = 3                           # Unique device identifier
DEVICE_NAME = f"Noise Monitor Node {NODE_ID}"

# Audio settings
SAMPLE_RATE = 44100                   # Audio sample rate
THRESHOLD = 86.0                      # dB threshold for events

# Calibration (adjust for your setup)
CALIBRATION_SPL = 94.0               # Reference SPL
CALIBRATION_RMS = 0.15               # Reference RMS

# Location (update with actual coordinates)
LAT = 12.9716                        # Latitude
LONG = 77.5946                       # Longitude
`

### MQTT Configuration

`python
MQTT_ENABLED = True
MQTT_BROKER = "192.168.1.35"         # Your MQTT broker IP
MQTT_PORT = 1883                     # MQTT port
USERNAME = "your_username"           # MQTT username
PASSWORD = "your_password"           # MQTT password
`

### File Paths (Linux deployment)

`python
DATA_PATH = "/home/rootpi/Noise_monitor"
CLIP_DIR = os.path.join(DATA_PATH, "clips")     # Audio clips
PLOT_DIR = os.path.join(DATA_PATH, "plots")     # Analysis plots
`

## 🎯 Usage

### Basic Operation

# Run with debug logging
python noise_monitor_updated.py --debug

# Run in background (Linux)
nohup python noise_monitor_updated.py &
`

### Command Line Options
- --debug: Enable detailed debug logging
- No options: Run in normal mode

### Monitoring Output
`
Noise Monitor Node 3 started – Standalone + MQTT mode
MQTT connected ✔
Monitoring noise levels... (Ctrl+C to stop)

[12:00:00] SPL: 45.2 dB | Real: 45.8 dB | Status: normal | High Events: 0 | Hourly Count: 0
[12:00:01] SPL: 87.5 dB | Real: 87.1 dB | Status: LOUD!!! | High Events: 1 | Hourly Count: 1
Saved: /home/rootpi/Noise_monitor/clips/Noisevent_0_87.5_20260428_120001.wav
Analysis done: /home/rootpi/Noise_monitor/plots/Noisevent_87.5_0 frequency plot.png
`

## 📡 MQTT Topics

### Real-time SPL Data
**Topic**: 
oise_monitor/node_{NODE_ID}/spl
`json
{
  "spl": 72.5,
  "raw_spl": 71.8,
  "rms": 0.000123,
  "timestamp": "2026-04-28T12:00:00.123456"
}
`

### System Status
**Topic**: 
oise_monitor/node_{NODE_ID}/status
`json
{
  "status": "normal"
}
`

### Hourly Statistics
**Topic**: 
oise_monitor/node_{NODE_ID}/hourly
`json
{
  "hour": 14,
  "hourly_max": 89.2,
  "hourly_avg": 65.8,
  "hourly_samples": 7200,
  "hourly_high_events": 5,
  "timestamp": "2026-04-28T14:30:00.123456"
}
`

### Noise Events
**Topic**: 
noise_monitor/node_{NODE_ID}/clip
`json
{
  "file": "/home/rootpi/Noise_monitor/clips/Noisevent_0_87.5_20260428_120001.wav",
  "plot": "/home/rootpi/Noise_monitor/plots/Noisevent_87.5_0 frequency plot.png",
  "L10": 92.3,
  "L50": 85.1,
  "L90": 78.9,
  "event_spl": 87.5
}
`

### Location Data
**Topic**: 
noise_monitor/node_{NODE_ID}/location
`json
{
  "latitude": 12.9716,
  "longitude": 77.5946
}
`

## 🏠 Home Assistant Integration

### Automatic Discovery
The system automatically creates sensors in Home Assistant:

1. **Real-time SPL Sensor**: Current noise level
2. **Status Sensor**: System status (diagnostic)
3. **Hourly Events Sensor**: High noise event counter
4. **Latitude Sensor**: Device latitude
5. **Longitude Sensor**: Device longitude

### Manual Configuration (Alternative)
If auto-discovery doesn't work, add to configuration.yaml:

`yaml
mqtt:
  sensor:
    - name: "Noise Level Node 3"
      state_topic: "noise_monitor/node_3/spl"
      value_template: "{{ value_json.spl }}"
      unit_of_measurement: "dB"
      device_class: sound_pressure
      json_attributes_topic: "noise_monitor/node_3/spl"
`

### Dashboard Example
Create a dashboard card showing:
- Current noise level gauge
- Hourly event counter
- Status indicator
- Location map

## 🔧 Calibration

### SPL Calibration Process

1. **Prepare Reference**: Use a calibrated sound level meter
2. **Generate Test Signal**: Play a known reference tone (94 dB at 1kHz)
3. **Measure Script Output**: Run the script and note RMS value
4. **Adjust Constants**:

`python
# If script shows 0.12 RMS for 94 dB reference:
CALIBRATION_SPL = 94.0
CALIBRATION_RMS = 0.12
`

### Verification
- Compare script readings with reference meter
- Test across different volume levels
- Recalibrate when changing microphones

## 🔍 Troubleshooting

### Audio Issues

# Check audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"

# Test basic recording
python -c "
import sounddevice as sd
import numpy as np
audio = sd.rec(44100, samplerate=44100, channels=1)
sd.wait()
print(f'RMS: {np.sqrt(np.mean(audio**2)):.6f}')
"
`

### MQTT Connection

# Test MQTT connection
python -c "
import paho.mqtt.client as mqtt
client = mqtt.Client()
client.connect('YOUR_BROKER_IP', 1883)
client.publish('test/topic', 'Hello World')
client.disconnect()
print('MQTT test successful')
"
`
### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| No audio input | RMS always 0 | Check microphone permissions, device index |
| MQTT connection fails | "MQTT unavailable" | Verify broker IP, credentials, firewall |
| High CPU usage | System slow | Reduce analysis frequency, check audio buffer |
| Files not saving | No clips/plots | Check write permissions, disk space |
| HA not discovering | No entities | Clear HA cache, check MQTT topics |

### Debug Mode
Run with --debug flag for detailed logging:
python noise_monitor_updated.py --debug
`

##  Contributing

1. Fork the repository
2. Create a feature branch (git checkout -b feature/amazing-feature)
3. Commit your changes (git commit -m 'Add amazing feature')
4. Push to the branch (git push origin feature/amazing-feature)
5. Open a Pull Request

### Development Setup

# Install development dependencies
pip install -r requirements.txt

# Run tests
python -m pytest

# Format code
black .
`

##  License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

##  Acknowledgments

- Sound analysis algorithms based on standard acoustic measurement practices
- MQTT integration inspired by Home Assistant community standards
- Frequency analysis using FFT and octave band filtering techniques

##  Support

For issues and questions:
- Open an issue on GitHub
- Check the troubleshooting section
- Review the detailed documentation in NOISE_LEVEL_DETECTION.md

---

**Note**: This system is designed for environmental monitoring and research purposes. Ensure compliance with local privacy laws when deploying audio recording systems.
