#!/usr/bin/env python3

import numpy as np
import sounddevice as sd
import time
import json
import sys
from datetime import datetime
import argparse
import os
import wave
import threading
import librosa
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt

# =================== ARGUMENT PARSING ===================
parser = argparse.ArgumentParser(description="Robust Noise Level Monitor (Standalone + MQTT)")
parser.add_argument('--debug', action='store_true', help="Enable detailed debug logging")
args = parser.parse_args()

DEBUG = args.debug

def debug_print(*msg):
    if DEBUG:
        print(f"[DEBUG {time.strftime('%H:%M:%S')}]", *msg)

# ================= CONFIG =================
LAT = 0.11
LONG = 0.22
NODE_ID = 3 
DEVICE_NAME = f"Noise Monitor Node {NODE_ID}"
SAMPLE_RATE = 44100
BUFFER_SEC = 0.5
BLOCKSIZE = int(SAMPLE_RATE * 0.125)

THRESHOLD = 86.0
CALIBRATION_SPL = 94.0
CALIBRATION_RMS = 0.15

MIN_DISPLAY_SPL = 40.0
EMA_ALPHA = 0.82
DECAY_ALPHA = 0.15
SILENCE_RMS = 0.0005


CLIP_SEC = 5                                #Record 5 seconds for each event (adjust as needed)
DATA_PATH = "/home/rootpi/Noise_monitor"     # Base path for clips and plots
CLIP_DIR = os.path.join(DATA_PATH, "clips")   # Directory to save audio clips
PLOT_DIR = os.path.join(DATA_PATH, "plots")   # Directory to save analysis plots

os.makedirs(CLIP_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

# ================= MQTT =================
MQTT_ENABLED = True
MQTT_BROKER = "192.168.1.35"
MQTT_PORT = 1883
USERNAME = "forest"
PASSWORD = "forest123"

TOPIC_SPL = f"noise_monitor/node_{NODE_ID}/spl"
TOPIC_CLIP = f"noise_monitor/node_{NODE_ID}/clip"
TOPIC_HOURLY = f"noise_monitor/node_{NODE_ID}/hourly"
TOPIC_STATUS = f"noise_monitor/node_{NODE_ID}/status"
TOPIC_LOCATION = f"noise_monitor/node_{NODE_ID}/location"

DISCOVERY_SPL = f"homeassistant/sensor/noise_node_{NODE_ID}/realtime/config"
DISCOVERY_HOURLY = f"homeassistant/sensor/noise_node_{NODE_ID}/hourly_stats/config"
#### newly Added the noise level status discovery topic for Home Assistant
DISCOVERY_STATUS = f"homeassistant/sensor/noise_node_{NODE_ID}/status/config"
DISCOVERY_LAT = f"homeassistant/sensor/noise_node_{NODE_ID}/latitude/config"
DISCOVERY_LON = f"homeassistant/sensor/noise_node_{NODE_ID}/longitude/config"
DISCOVERY_CLIP = f"homeassistant/sensor/noise_node_{NODE_ID}/clip/config"
# ================= AUDIO BUFFERS =================
buffer = np.zeros(int(SAMPLE_RATE * BUFFER_SEC), dtype=np.float32)
clip_buffer = np.zeros(int(SAMPLE_RATE * CLIP_SEC), dtype=np.float32)

buffer_ptr = 0
clip_ptr = 0
spl_ema = 0.0
last_process = time.time()

hourly_values = []
last_hour = datetime.now().hour
high_event_count = 0
hourly_high_event_count = 0
Noise_counter = 0

mqtt_ok = False
clip_saved_for_event = False
detected = False

# =================== MQTT HELPERS ===================
client = mqtt.Client()
client.username_pw_set(USERNAME, PASSWORD)

def mqtt_publish(topic, payload, retain=False):
    global mqtt_ok
    if not MQTT_ENABLED or not mqtt_ok:
        return
    try:
        client.publish(topic, payload, retain=retain)
    except Exception as e:
        debug_print(f"MQTT publish failed on {topic}: {e}")
        mqtt_ok = False
        
def send_discovery():
    device_info = {
        "identifiers": [f"noise_node_{NODE_ID}"],
        "name": f"Noise Detector Node {NODE_ID}",
        "manufacturer": "Custom",
        "model": "Noise SPL Monitor V1"
    }

    # Real-time SPL sensor
    mqtt_publish(DISCOVERY_SPL, json.dumps({
        "name": f"Noise Level Node {NODE_ID}",
        "unique_id": f"noise_realtime_spl_node_{NODE_ID}",
        "state_topic": TOPIC_SPL,
        "value_template": "{{ value_json.spl }}",
        "unit_of_measurement": "dB",
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "json_attributes_topic": TOPIC_SPL,
        "device": device_info
    }), retain=True)
    
    # Status sensor (connectivity) - shows quiet/normal/LOUD
    mqtt_publish(DISCOVERY_STATUS, json.dumps({
        "name": f"Noise Status Node {NODE_ID}",
        "unique_id": f"noise_status_node_{NODE_ID}",
        "state_topic": TOPIC_STATUS,
        "value_template": "{{ value_json.status }}",
        "entity_category": "diagnostic",
        "device": device_info
    }), retain=True)
  
    # Hourly stats sensor (current hour event count as state)
    mqtt_publish(DISCOVERY_HOURLY, json.dumps({
        "name": f"Noise Hourly Stats Node {NODE_ID}",
        "unique_id": f"noise_hourly_stats_node_{NODE_ID}",
        "state_topic": TOPIC_HOURLY,
        "value_template": "{{ value_json.hourly_high_events }}",
        "state_class": "measurement",
        "json_attributes_topic": TOPIC_HOURLY,
        "device": device_info
    }), retain=True)
    
    # Latitude sensor
    mqtt_publish(DISCOVERY_LAT, json.dumps({
        "name": f"Noise Node {NODE_ID} Latitude",
        "unique_id": f"noise_lat_node_{NODE_ID}",
        "state_topic": TOPIC_LOCATION,
        "value_template": "{{ value_json.latitude }}",
        "unit_of_measurement": "°",
        "device": device_info
    }), retain=True)
    
    # Longitude sensor
    mqtt_publish(DISCOVERY_LON, json.dumps({
        "name": f"Noise Node {NODE_ID} Longitude",
        "unique_id": f"noise_lon_node_{NODE_ID}",
        "state_topic": TOPIC_LOCATION,
        "value_template": "{{ value_json.longitude }}",
        "unit_of_measurement": "°",
        "device": device_info
    }), retain=True)
    
    mqtt_publish(DISCOVERY_CLIP, json.dumps({
        "name": f"Noise Clip Event Node {NODE_ID}",
        "unique_id": f"noise_clip_event_node_{NODE_ID}",
        "state_topic": TOPIC_CLIP,
        "value_template": "{{ value_json.event_spl }}",
        "unit_of_measurement": "dB",
        "device_class": "sound_pressure",
        "state_class": "measurement",
        "json_attributes_topic": TOPIC_CLIP,
        "json_attributes_template": "{{ value_json | tojson }}",
        "device": device_info
    }), retain=True)
      
def on_connect(client, userdata, flags, rc):
    global mqtt_ok
    if rc == 0:
        mqtt_ok = True
        print("MQTT connected ✔")
        client.publish(TOPIC_STATUS, "online", retain=True)
        send_discovery()
        # Publish location data once
        mqtt_publish(TOPIC_LOCATION, json.dumps({
            "latitude": LAT,
            "longitude": LONG
        }), retain=True)
    else:
        mqtt_ok = False
        print(f"MQTT connect failed, rc={rc}")

def on_disconnect(client, userdata, rc):
    global mqtt_ok
    mqtt_ok = False
    print(f"MQTT disconnected (rc={rc})")

client.on_connect = on_connect
client.on_disconnect = on_disconnect

def connect_mqtt():
    global mqtt_ok
    if not MQTT_ENABLED:
        return
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
    except Exception as e:
        mqtt_ok = False
        print(f"MQTT unavailable: {e}")
        print("Continuing in local mode without MQTT.")      

# =================== DEVICE AUTO-DETECTION ===================
def find_input_device():
    devices = sd.query_devices()
    candidates = []
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            candidates.append((i, dev))
            if DEBUG:
                debug_print(f"Found input device {i}: {dev['name']} ({dev['max_input_channels']} in)")

    if not candidates:
        print("ERROR: No audio input devices found!")
        sys.exit(1)

    for i, dev in candidates:
        if 'Go Mic' in dev['name'] or 'Samson' in dev['name']:
            print(f"Using Samson Go Mic → device {i}: {dev['name']}")
            return i

    best_i, best_dev = candidates[0]
    print(f"Using input device {best_i}: {best_dev['name']}")
    return best_i

DEVICE_INDEX = find_input_device()


# ================= AUDIO CALLBACK =================
def audio_callback(indata, frames, time_info, status):
    global buffer_ptr, clip_ptr

    mono = indata[:, 0]

    # rolling buffer
    end = buffer_ptr + len(mono)
    if end <= len(buffer):
        buffer[buffer_ptr:end] = mono
    else:
        split = len(buffer) - buffer_ptr
        buffer[buffer_ptr:] = mono[:split]
        buffer[:end % len(buffer)] = mono[split:]
    buffer_ptr = end % len(buffer)

    # clip buffer
    end = clip_ptr + len(mono)
    if end <= len(clip_buffer):
        clip_buffer[clip_ptr:end] = mono
    else:
        split = len(clip_buffer) - clip_ptr
        clip_buffer[clip_ptr:] = mono[:split]
        clip_buffer[:end % len(clip_buffer)] = mono[split:]
    clip_ptr = end % len(clip_buffer)

# ================= ANALYSIS =================
CENTER_FREQS = [25,31.5,40,50,63,80,100,125,160,200,
                250,315,400,500,630,800,1000,1250,1600,
                2000,2500,3150,4000,5000,6300,8000]

def analyze_and_plot(file_path, current_spl=None, counter=None):
    BLOCK_SEC = 0.125
    CALIBRATION_OFFSET = 94.0
    
    def third_octave(chunk, fs):
        N = len(chunk)
        window = np.hanning(N)
        window_loss_correction = np.sum(window**2) 
        
        spectrum = (np.abs(np.fft.rfft(chunk * window))**2) / window_loss_correction
        freqs = np.fft.rfftfreq(N, d=1/fs)

        levels = []
        for fc in CENTER_FREQS:
            fl, fh = fc/(2**(1/6)), fc*(2**(1/6))
            idx = np.where((freqs >= fl) & (freqs < fh))[0]
            if len(idx):
                power = np.sum(spectrum[idx])
                db = 10*np.log10(power + 1e-12) + CALIBRATION_OFFSET
                levels.append(max(0, db))
            else:
                levels.append(0)
        return np.array(levels)

    # --- Load Audio ---
    y, sr = librosa.load(file_path, sr=None)
    block = int(sr * BLOCK_SEC)
    bands_all = []
    spl_all = []

    for i in range(0, len(y) - block, block):
        chunk = y[i:i+block]
        bands = third_octave(chunk, sr)
        total_power = np.sum(10**(bands/10))
        spl = 10*np.log10(total_power + 1e-12)
        bands_all.append(bands)
        spl_all.append(spl)

    bands_avg = np.mean(bands_all, axis=0)
    
    # Statistical levels
    L10 = np.percentile(spl_all, 90)
    L50 = np.percentile(spl_all, 50)
    L90 = np.percentile(spl_all, 10)

    # ---- IMPROVED PLOT SECTION ----
    plt.style.use('seaborn-v0_8-whitegrid') 
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8f8f8') 
    
    # Create the bars
    x_labels = [str(f) for f in CENTER_FREQS]
    ax.bar(x_labels, bands_avg, color='steelblue', edgecolor='black', alpha=0.8)

    # Labels and Titles
    ax.set_xlabel("Frequency (Hz)", fontsize=12, fontweight='bold')
    ax.set_ylabel("Sound Pressure Level (dB)", fontsize=12, fontweight='bold')
    
    # Main Heading and Subheading (SPL Metrics)
    title = f"SPL Metrics: L10={L10:.1f} dB | L50={L50:.1f} dB | L90={L90:.1f} dB"
    if current_spl is not None:
        title += f" | Event SPL: {current_spl:.1f} dB"
    plt.suptitle("1/3 Octave Band Frequency Analysis", fontsize=16, fontweight='bold')
    ax.set_title(title, fontsize=11, color='#444444', pad=10)

    # Formatting ticks
    plt.xticks(rotation=45, fontsize=9)
    plt.yticks(np.arange(0, max(bands_avg) + 20, 10)) # Adjust Y-axis scale dynamically
    
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95]) # Adjust layout to fit suptitle

    if current_spl is not None and counter is not None:
        plot_filename = f"Noisevent_{current_spl:.1f}_{counter} frequency plot.png"
    else:
        plot_filename = os.path.basename(file_path).replace(".wav", ".png")
    plot_file = os.path.join(PLOT_DIR, plot_filename)
    plt.savefig(plot_file, dpi=150)
    plt.close()

    return plot_file, L10, L50, L90

# ================= SAVE CLIP =================
def save_clip(current_spl):
    global Noise_counter
    audio = np.copy(clip_buffer)

    filename = os.path.join(CLIP_DIR, f"Noisevent_{Noise_counter}_{current_spl:.1f}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")

    scaled = np.int16(np.clip(audio, -1, 1) * 32767)

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(scaled.tobytes())

    print("Saved:", filename)
    Noise_counter += 1

    # run analysis async
    threading.Thread(target=run_analysis, args=(filename, current_spl, Noise_counter - 1)).start()

def run_analysis(file, current_spl, counter):
    try:
        plot, L10, L50, L90 = analyze_and_plot(file, current_spl, counter)

        print("Analysis done:", plot)

        mqtt_publish(TOPIC_CLIP, json.dumps({
            "file": str(file),
            "plot": str(plot),
             "L10": round(float(L10), 1),
             "L50": round(float(L50), 1),
             "L90": round(float(L90), 1),
             "event_spl": round(float(current_spl), 1) if current_spl is not None else None
        }))

    except Exception as e:
        print("Analysis error:", e)

# ================= MAIN =================
print(f"{DEVICE_NAME} started – Standalone + MQTT mode")
if DEBUG:
    print("DEBUG mode enabled – detailed logs active")
    debug_print("Config → Sample rate:", SAMPLE_RATE,
                "| Buffer sec:", BUFFER_SEC,
                "| Blocksize:", BLOCKSIZE)
    debug_print(f"Threshold: {THRESHOLD} dB | Calibration: {CALIBRATION_SPL} dB @ RMS {CALIBRATION_RMS}")

connect_mqtt()

# Try stream with plughw first, fall back to direct device index
stream = None

try:
    debug_print("Trying plughw device...")
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        device=f"plughw:{DEVICE_INDEX}",
        channels=1,
        callback=audio_callback,
        blocksize=BLOCKSIZE,
        dtype='float32',
        latency='low'
    )
    stream.start()
    debug_print("Audio stream started successfully with plughw")
except Exception as e:
    debug_print("plughw failed:", e)
    
if stream is None:
    print("plughw not available → falling back to direct device")
    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            device=DEVICE_INDEX,
            channels=1,
            callback=audio_callback,
            blocksize=BLOCKSIZE,
            dtype='float32',
            latency='low'
        )
        stream.start()
        debug_print("Audio stream started successfully with direct device")
    except Exception as e:
        print(f"Failed to start audio stream even with direct device: {e}")
        print("Run 'python3 -m sounddevice' and check your mic")
        sys.exit(1)    
    
      
    
spl_ema = 0

print("Monitoring noise levels... (Ctrl+C to stop)\n")

try:
    while True:
        if time.time() - last_process >= BUFFER_SEC:
            last_process = time.time()

            audio = np.copy(buffer)
            rms = np.sqrt(np.mean(audio**2) + 1e-12)
            raw_spl = CALIBRATION_SPL + 20 * np.log10(rms / CALIBRATION_RMS)
            debug_print(f"Raw RMS: {rms:.6f} → Raw SPL: {raw_spl:.2f} dB")

            now = datetime.now()

            if rms < SILENCE_RMS:
                spl_ema *= 0.9
                detected = False
                status = "quiet"
                display_spl = 0.0
                debug_print("Silence detected")
            else:
                if raw_spl > spl_ema:
                    spl_ema = EMA_ALPHA * raw_spl + (1 - EMA_ALPHA) * spl_ema
                else:
                    spl_ema = DECAY_ALPHA * raw_spl + (1 - DECAY_ALPHA) * spl_ema

                detected = spl_ema > THRESHOLD
                status = "LOUD!!!" if detected else "normal"
                display_spl = max(MIN_DISPLAY_SPL, spl_ema) if detected else round(spl_ema, 1)

                if detected:
                    high_event_count += 1
                    hourly_high_event_count += 1

            # Hourly stats rollover
            if now.hour != last_hour:
                if len(hourly_values) > 0:
                    hourly_max = max(hourly_values)
                    hourly_avg = sum(hourly_values) / len(hourly_values)

                    print(f"\n=== Hourly Summary (Hour {last_hour:02d}) ===")
                    print(f"   Max: {hourly_max:.1f} dB | Avg: {hourly_avg:.1f} dB | High Events: {hourly_high_event_count}")
                    print("==============================================\n")

                    mqtt_publish(TOPIC_HOURLY, json.dumps({
                        "hour": last_hour,
                        "hourly_max": float(round(hourly_max, 1)),
                        "hourly_avg": float(round(hourly_avg, 1)),
                        "hourly_samples": len(hourly_values),
                        "hourly_high_events": hourly_high_event_count
                    }), retain=True)

                hourly_values = [spl_ema]
                last_hour = now.hour
                hourly_high_event_count = 0
            else:
                hourly_values.append(spl_ema)

            # Publish real-time MQTT data status and time stamp
            mqtt_publish(TOPIC_SPL, json.dumps({
                "spl": round(float(display_spl), 1),
                "raw_spl": round(float(raw_spl), 2),
                "rms": round(float(rms), 6),
                 "timestamp": now.isoformat()
            }), retain=True)
            
            mqtt_publish(TOPIC_STATUS, json.dumps({
                "status": status,
             
            }), retain=True)
            

            mqtt_publish(TOPIC_HOURLY, json.dumps({
                "hour": last_hour,
                "hourly_max": float(round(max(hourly_values), 1)) if hourly_values else 0.0,
                "hourly_avg": float(round(sum(hourly_values) / len(hourly_values), 1)) if hourly_values else 0.0,
                "hourly_samples": len(hourly_values),
                "hourly_high_events": hourly_high_event_count,
                "timestamp": now.isoformat()
            }), retain=True)

            print(f"[{now.strftime('%H:%M:%S')}] SPL: {display_spl:.1f} dB | "
                  f"Real: {spl_ema:.2f} dB | Status: {status} | "
                  f"High Events: {high_event_count} | Hourly Count: {hourly_high_event_count}")

            debug_print(f"EMA: {spl_ema:.4f} | Detected: {detected} | Hourly samples: {len(hourly_values)}")
            
            if detected and not clip_saved_for_event:
                save_clip(spl_ema)
                clip_saved_for_event = True
            elif not detected:
                clip_saved_for_event = False
            
        time.sleep(0.01)

except KeyboardInterrupt:
    print(f"\n\n{DEVICE_NAME} stopped by user.")
finally:
    if stream:
        stream.stop()
        stream.close()

    if MQTT_ENABLED:
        try:
            client.publish(TOPIC_STATUS, "offline", retain=True)
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

    print("Audio stream closed cleanly.")
