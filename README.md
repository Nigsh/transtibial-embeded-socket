# SmartFit — Socket Fitting System

Transtibial (below-knee) prosthetic socket pressure simulation pipeline.
12x Interlink 402 FSR sensors | ESP32 BLE | White/Black/Brown UI

---

## Project Structure

```
smartfit/
├── pressure_calculator.py   Stage 1 — ideal pressure baseline (biomechanical model)
├── fsr_sensor.py            Stage 2 — FSR sensor data (simulated or live BLE)
├── analysis_engine.py       Stage 3+4 — deviation analysis, FQS, recommendations
├── pipeline.py              Orchestrator — ties all stages together
├── app.py                   Flask web server + heatmap UI
├── requirements.txt         Python dependencies
└── README.md                This file
```

---

## Setup (one time)

```bash
# 1. Install Flask (only dependency)
pip install -r requirements.txt

# 2. You're ready.
```

---

## Run the Web UI

```bash
python app.py
```
Then open **http://localhost:5000** in your browser.

1. Fill in patient name, weight, residuum length, socket tightness
2. Choose activity level
3. Select a fault to simulate (or "None" for ideal fit)
4. Click **Run Analysis**
5. See the heatmap, Fit Quality Score, and adjustment recommendations

---

## Run Headless (terminal only)

```bash
# Single patient, ideal fit
python pipeline.py --name "Abebe" --weight 70 --length 14 --tight 1.0 --fault none

# With fault injection
python pipeline.py --name "Tigist" --weight 55 --length 12 --tight 0.95 --fault tibia

# Run all demo cases
python pipeline.py --demo
```

---

## Run Individual Stages

```bash
python pressure_calculator.py   # Stage 1 — ideal pressures
python fsr_sensor.py            # Stage 2 — streaming FSR output
python analysis_engine.py       # Stage 3+4 — full analysis
```

---

## Fault Types (simulation)

| Fault      | Description                         | Clinical presentation          |
|------------|-------------------------------------|-------------------------------|
| none       | Ideal fit                           | All zones optimal              |
| tibia      | Anterior tibia crest over-loaded    | Skin redness on tibia crest    |
| distal     | Distal end over-loaded              | End-bearing pain               |
| medial     | Medial bony prominence              | Pain at tibial flare           |
| posterior  | Posterior calf slack                | Socket pistoning               |
| multi      | Multi-zone mismatch                 | Multiple discomfort points     |

---

## Connecting Real ESP32 Hardware

Replace `SimulatedFSR` with `BleFSR` in `pipeline.py`:

```python
# In pipeline.py, Stage 2:
from fsr_sensor import BleFSR
# ...
async with BleakClient(DEVICE_ADDRESS) as client:
    fsr = BleFSR(client)
    frame = await fsr.read_frame()
```

BLE UUIDs are defined in `fsr_sensor.py` (BleFSR class).

---

## References

- Swanson et al. (2019) J. Biomech. Eng. 141(10)
- Young et al. (2023) Expert Review of Medical Devices 20(10)
- Graser et al. (2020) BMC Biomedical Engineering 2
- Sanders & Fatone (2011) Phys. Med. Rehab. Clin. N. Am. 22(1)
