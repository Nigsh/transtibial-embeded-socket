"""
SmartFit | fsr_sensor.py
=========================
Stage 2 — FSR sensor data layer.

In production this module reads live data from 12x Interlink 402 FSR
sensors via ESP32 over BLE (Section 8.2 of SmartFit paper).

Until the hardware is available, SimulatedFSR generates realistic
sensor readings by applying:
  • Anatomical fault multipliers (poor-fit pressure redistribution)
  • Multiplicative Gaussian noise  (±10% drift, matches NFR1 spec)
  • ADC quantisation (12-bit, 0–4095)
  • 10 Hz averaged sampling

To switch to real hardware later, replace SimulatedFSR with
BleFSR (stub provided at the bottom of this file).

Run standalone to stream simulated sensor readings:
    python fsr_sensor.py
"""

from __future__ import annotations
import random
import time
import dataclasses
from enum import Enum
from typing import List, Optional, Dict


# ---------------------------------------------------------------------------
# Fault presets — inject a known fitting error for simulation / testing
# ---------------------------------------------------------------------------

class FaultType(str, Enum):
    NONE      = "none"       # Ideal fit — no fault
    TIBIA     = "tibia"      # Anterior tibia crest over-loaded
    DISTAL    = "distal"     # Distal end over-loaded
    MEDIAL    = "medial"     # Medial bony prominence over-loaded
    POSTERIOR = "posterior"  # Posterior region under-loaded (loose suspension)
    MULTI     = "multi"      # Multi-zone mismatch


# Per-sensor pressure multipliers for each fault (12 values, one per sensor)
FAULT_MULTIPLIERS: Dict[FaultType, List[float]] = {
    FaultType.NONE:      [1.0]*12,
    FaultType.TIBIA:     [1.9, 1.7, 1.1, 0.8, 0.9, 1.0, 0.9, 1.0, 0.8, 0.8, 1.0, 1.0],
    FaultType.DISTAL:    [1.0, 1.0, 1.2, 1.0, 1.0, 1.1, 1.0, 1.0, 0.9, 0.9, 2.1, 1.3],
    FaultType.MEDIAL:    [1.0, 1.0, 1.0, 1.8, 1.6, 1.3, 0.7, 0.8, 1.0, 1.0, 1.0, 1.0],
    FaultType.POSTERIOR: [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.3, 0.3, 1.0, 1.0],
    FaultType.MULTI:     [1.7, 1.2, 1.0, 1.6, 1.0, 0.7, 0.7, 1.5, 0.4, 1.7, 1.8, 1.0],
}


# ---------------------------------------------------------------------------
# Single sensor reading
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class SensorFrame:
    """One snapshot of all 12 FSR sensors."""
    timestamp: float              # Unix time
    raw_adc: List[int]            # 12-bit ADC values (0–4095)
    pressure_kpa: List[float]     # Converted pressure values (kPa)
    sensor_count: int = 12

    def to_dict(self) -> Dict:
        return {
            "timestamp": round(self.timestamp, 3),
            "raw_adc": self.raw_adc,
            "pressure_kpa": [round(p, 2) for p in self.pressure_kpa],
        }


# ---------------------------------------------------------------------------
# ADC ↔ pressure conversion (Interlink 402 characteristic curve)
# ---------------------------------------------------------------------------

class FSRConverter:
    """
    Converts ADC counts → force (g) → pressure (kPa).

    Interlink 402 datasheet: R ∝ 1/F, with typical conductance curve.
    With a 10 kΩ voltage divider and 3.3 V supply on the ESP32:
        V_out = 3.3 * (R_fixed / (R_fixed + R_FSR))
    We linearise over the 0.2 N – 20 N operating range.
    Active area = 1 cm² = 1e-4 m²
    """
    ADC_MAX      = 4095
    V_SUPPLY     = 3.3
    R_FIXED      = 10_000      # Ω voltage divider resistor
    FSR_AREA_M2  = 1e-4        # m²

    # Empirical calibration constants for Interlink 402
    # F (grams) = A * (ADC / ADC_MAX) ^ B
    CALIB_A = 2000.0
    CALIB_B = 1.8

    def adc_to_kpa(self, adc: int) -> float:
        if adc <= 0:
            return 0.0
        ratio = adc / self.ADC_MAX
        force_g = self.CALIB_A * (ratio ** self.CALIB_B)
        force_n = force_g * 9.81 / 1000.0
        pressure_pa = force_n / self.FSR_AREA_M2
        return pressure_pa / 1000.0   # kPa

    def kpa_to_adc(self, kpa: float) -> int:
        if kpa <= 0:
            return 0
        pressure_pa = kpa * 1000.0
        force_n = pressure_pa * self.FSR_AREA_M2
        force_g = force_n * 1000.0 / 9.81
        ratio = (force_g / self.CALIB_A) ** (1.0 / self.CALIB_B)
        return min(self.ADC_MAX, max(0, int(ratio * self.ADC_MAX)))


# ---------------------------------------------------------------------------
# Simulated FSR (no hardware required)
# ---------------------------------------------------------------------------

class SimulatedFSR:
    """
    Simulates 12x Interlink 402 FSR sensors at 10 Hz.

    Parameters
    ----------
    ideal_kpa   : ideal pressure baseline (from PressureCalculator)
    fault       : which fitting fault to inject
    noise       : Gaussian noise level (0.05 = ±10% per NFR1 spec)
    seed        : random seed for reproducibility
    """

    SAMPLE_RATE_HZ = 10

    def __init__(
        self,
        ideal_kpa: List[float],
        fault: FaultType = FaultType.NONE,
        noise: float = 0.05,
        seed: Optional[int] = None,
    ):
        if not 0.0 <= noise <= 0.20:
            raise ValueError("noise must be in [0.0, 0.20]")
        self.ideal_kpa = ideal_kpa
        self.fault = fault
        self.noise = noise
        self._rng = random.Random(seed)
        self._converter = FSRConverter()
        self._mods = FAULT_MULTIPLIERS[fault]

    def read_frame(self) -> SensorFrame:
        """Capture one frame of 12 sensor readings."""
        measured_kpa = []
        raw_adc = []
        for i, ideal in enumerate(self.ideal_kpa):
            noise_factor = 1.0 + self._rng.gauss(0, self.noise)
            kpa = max(0.0, ideal * self._mods[i] * noise_factor)
            measured_kpa.append(round(kpa, 2))
            raw_adc.append(self._converter.kpa_to_adc(kpa))
        return SensorFrame(
            timestamp=time.time(),
            raw_adc=raw_adc,
            pressure_kpa=measured_kpa,
        )

    def stream(self, frames: int = 10, delay: bool = True):
        """
        Generator that yields SensorFrame objects at SAMPLE_RATE_HZ.
        Set delay=False for fast batch simulation.
        """
        for _ in range(frames):
            yield self.read_frame()
            if delay:
                time.sleep(1.0 / self.SAMPLE_RATE_HZ)

    def averaged_frame(self, n_samples: int = 10) -> SensorFrame:
        """
        Collect n_samples frames and return a time-averaged frame.
        Mirrors the ESP32 firmware averaging described in Section 8.2.
        """
        frames = list(self.stream(frames=n_samples, delay=False))
        avg_kpa = [
            sum(f.pressure_kpa[i] for f in frames) / n_samples
            for i in range(12)
        ]
        avg_adc = [
            int(sum(f.raw_adc[i] for f in frames) / n_samples)
            for i in range(12)
        ]
        return SensorFrame(
            timestamp=time.time(),
            raw_adc=avg_adc,
            pressure_kpa=avg_kpa,
        )


# ---------------------------------------------------------------------------
# BLE FSR stub (replace SimulatedFSR with this when hardware is ready)
# ---------------------------------------------------------------------------

class BleFSR:
    """
    STUB — replace SimulatedFSR with this for real ESP32 BLE integration.

    BLE characteristic UUIDs match the SmartFit ESP32 firmware (Section 8.2):
        Service UUID:     "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
        Char UUID:        "beb5483e-36e1-4688-b7f5-ea07361b26a8"

    Expected BLE packet: 24 bytes
        [sensor_id(1)] [adc_high(1)] [adc_low(1)] × 12 sensors = 36 bytes
        Sent every 100 ms (10 Hz)

    Usage (requires bleak library: pip install bleak):
        import asyncio
        from bleak import BleakClient
        async def connect():
            async with BleakClient(DEVICE_ADDRESS) as client:
                fsr = BleFSR(client)
                frame = await fsr.read_frame()
    """

    SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
    CHAR_UUID    = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

    def __init__(self, ble_client):
        self._client = ble_client
        self._converter = FSRConverter()

    async def read_frame(self) -> SensorFrame:
        data = await self._client.read_gatt_char(self.CHAR_UUID)
        raw_adc = []
        for i in range(12):
            high = data[i * 2]
            low  = data[i * 2 + 1]
            raw_adc.append((high << 8) | low)
        pressure_kpa = [self._converter.adc_to_kpa(v) for v in raw_adc]
        return SensorFrame(
            timestamp=time.time(),
            raw_adc=raw_adc,
            pressure_kpa=pressure_kpa,
        )


# ---------------------------------------------------------------------------
# Standalone demo — stream simulated readings
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pressure_calculator import PressureCalculator, PatientProfile

    patient = PatientProfile("Demo Patient", 35, 70.0, 14.0, 1.00, "moderate")
    baseline = PressureCalculator().calculate(patient)

    print(f"Streaming simulated FSR data — fault: TIBIA CREST\n")
    fsr = SimulatedFSR(baseline.ideal_kpa, fault=FaultType.TIBIA, noise=0.05, seed=42)

    for i, frame in enumerate(fsr.stream(frames=5, delay=False)):
        print(f"Frame {i+1:02d} | {len(frame.pressure_kpa)} sensors")
        for j, kpa in enumerate(frame.pressure_kpa):
            bar = "█" * int(kpa / 80)
            print(f"  S{j:02d}: {kpa:7.1f} kPa  {bar}")
        print()
