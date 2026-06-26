"""
SmartFit | pressure_calculator.py
==================================
Stage 1 — Biomechanical ideal pressure calculation.

Given patient parameters, computes the expected (ideal) pressure in kPa
at each of the 12 FSR sensor anatomical locations.

Biomechanical model references:
  - Swanson et al. (2019) J. Biomech. Eng. 141(10)
  - Graser et al. (2020) BMC Biomed. Eng. 2
  - Sanders & Fatone (2011) Phys. Med. Rehab. Clin. N. Am. 22(1)

Run standalone to see sample output:
    python pressure_calculator.py
"""

import math
import dataclasses
from typing import List, Dict


# ---------------------------------------------------------------------------
# Sensor layout — 12 FSR positions on the transtibial socket
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class SensorSpec:
    id: int
    name: str
    zone: str
    weight_fraction: float   # fraction of body weight borne at this sensor
    canvas_x: float          # 0-1 normalised x on unfolded socket diagram
    canvas_y: float          # 0-1 normalised y on unfolded socket diagram
    description: str         # clinical description


SENSORS: List[SensorSpec] = [
    SensorSpec(0,  "Ant. Tibia Crest (Proximal)",    "anterior",  0.14, 0.50, 0.12, "Weight-bearing tibial crest — highest anterior load"),
    SensorSpec(1,  "Ant. Mid-Shaft",                  "anterior",  0.10, 0.50, 0.34, "Mid-anterior shaft — moderate load zone"),
    SensorSpec(2,  "Ant. Distal",                     "anterior",  0.08, 0.50, 0.56, "Distal anterior — transition to end-bearing"),
    SensorSpec(3,  "Med. Tibial Flare (Proximal)",    "medial",    0.09, 0.34, 0.19, "Medial tibial flare — bony prominence risk"),
    SensorSpec(4,  "Med. Mid-Shaft",                  "medial",    0.08, 0.32, 0.42, "Medial mid-shaft — moderate load"),
    SensorSpec(5,  "Med. Distal",                     "medial",    0.07, 0.35, 0.62, "Medial distal — lower load zone"),
    SensorSpec(6,  "Lat. Fibular Head (Proximal)",    "lateral",   0.09, 0.66, 0.19, "Lateral fibular head — bony prominence risk"),
    SensorSpec(7,  "Lat. Mid-Shaft",                  "lateral",   0.07, 0.68, 0.42, "Lateral mid-shaft — moderate load"),
    SensorSpec(8,  "Post. Gastrocnemius (Medial)",    "posterior", 0.10, 0.23, 0.31, "Medial gastrocnemius belly — soft tissue load"),
    SensorSpec(9,  "Post. Gastrocnemius (Lateral)",   "posterior", 0.08, 0.77, 0.31, "Lateral gastrocnemius belly — soft tissue load"),
    SensorSpec(10, "Distal End-Bearing Pad",          "distal",    0.06, 0.50, 0.81, "Distal end — end-bearing load, DTI risk if high"),
    SensorSpec(11, "Proximal Brim (Circumferential)", "proximal",  0.04, 0.50, 0.96, "Proximal brim — suspension reference"),
]

assert abs(sum(s.weight_fraction for s in SENSORS) - 1.0) < 1e-9, \
    "Weight fractions must sum to 1.0"


# ---------------------------------------------------------------------------
# Patient profile
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class PatientProfile:
    name: str
    age: int
    body_weight_kg: float      # 40–120 kg
    residuum_length_cm: float  # 8–22 cm (knee to distal end)
    socket_tightness: float    # 0.5 loose → 1.0 ideal → 1.5 tight
    activity_level: str        # "low", "moderate", "high"

    def validate(self):
        errors = []
        if not 40 <= self.body_weight_kg <= 120:
            errors.append("Body weight must be 40–120 kg")
        if not 8 <= self.residuum_length_cm <= 22:
            errors.append("Residuum length must be 8–22 cm")
        if not 0.5 <= self.socket_tightness <= 1.5:
            errors.append("Socket tightness must be 0.5–1.5")
        if self.activity_level not in ("low", "moderate", "high"):
            errors.append("Activity level must be low, moderate, or high")
        if errors:
            raise ValueError(" | ".join(errors))


# ---------------------------------------------------------------------------
# Pressure calculation result
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class PressureBaseline:
    patient: PatientProfile
    ideal_kpa: List[float]           # one value per sensor
    length_factor: float
    activity_factor: float
    total_force_n: float

    def get(self, sensor_id: int) -> float:
        return self.ideal_kpa[sensor_id]

    def summary(self) -> str:
        lines = [
            "=" * 62,
            f"  Pressure Baseline — {self.patient.name}",
            "=" * 62,
            f"  Body weight:         {self.patient.body_weight_kg:.1f} kg",
            f"  Residuum length:     {self.patient.residuum_length_cm:.1f} cm",
            f"  Socket tightness:    {self.patient.socket_tightness:.2f}",
            f"  Activity level:      {self.patient.activity_level}",
            f"  Total stance force:  {self.total_force_n:.1f} N",
            f"  Length factor:       {self.length_factor:.3f}",
            f"  Activity factor:     {self.activity_factor:.3f}",
            "",
            f"  {'#':<3} {'Sensor':<38} {'Ideal kPa':>10}",
            "  " + "-" * 55,
        ]
        for s in SENSORS:
            lines.append(f"  {s.id:<3} {s.name:<38} {self.ideal_kpa[s.id]:>9.1f}")
        lines.append("=" * 62)
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "patient": dataclasses.asdict(self.patient),
            "total_force_n": round(self.total_force_n, 2),
            "length_factor": round(self.length_factor, 4),
            "activity_factor": round(self.activity_factor, 4),
            "sensors": [
                {
                    "id": s.id,
                    "name": s.name,
                    "zone": s.zone,
                    "ideal_kpa": round(self.ideal_kpa[s.id], 2),
                    "canvas_x": s.canvas_x,
                    "canvas_y": s.canvas_y,
                }
                for s in SENSORS
            ],
        }


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class PressureCalculator:
    """
    Computes the biomechanical ideal pressure at each of the 12 FSR
    sensor locations for a given patient profile.

    Physical model
    --------------
    During single-limb stance the socket bears the full body weight:
        F_total = m * g  [N]

    Each sensor i bears a fraction w_i of that force over the FSR
    active area (Interlink 402 ≈ 1 cm² = 1e-4 m²):
        P_i = (w_i * F_total * length_factor * tightness * activity_factor)
              / A_sensor  [Pa]  →  / 1000  [kPa]

    Length factor (Swanson 2019):
        Shorter residuums concentrate load → higher pressure.
        length_factor = (L / L_ref) ** -0.30
        L_ref = 14 cm

    Activity factor:
        Higher activity → greater dynamic loading.
        low=0.90, moderate=1.00, high=1.15
    """

    FSR_AREA_M2       = 1e-4     # Interlink 402 active area
    NOMINAL_LENGTH_CM = 14.0
    GRAVITY           = 9.81

    ACTIVITY_FACTORS = {
        "low": 0.90,
        "moderate": 1.00,
        "high": 1.15,
    }

    def calculate(self, patient: PatientProfile) -> PressureBaseline:
        patient.validate()

        F_total        = patient.body_weight_kg * self.GRAVITY
        length_factor  = (patient.residuum_length_cm / self.NOMINAL_LENGTH_CM) ** -0.30
        activity_factor = self.ACTIVITY_FACTORS[patient.activity_level]

        ideal_kpa = []
        for s in SENSORS:
            pressure_pa = (
                s.weight_fraction
                * F_total
                * length_factor
                * patient.socket_tightness
                * activity_factor
            ) / self.FSR_AREA_M2
            ideal_kpa.append(pressure_pa / 1000.0)

        return PressureBaseline(
            patient=patient,
            ideal_kpa=ideal_kpa,
            length_factor=length_factor,
            activity_factor=activity_factor,
            total_force_n=F_total,
        )


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    calc = PressureCalculator()

    patients = [
        PatientProfile("Abebe Girma",  35, 70.0, 14.0, 1.00, "moderate"),
        PatientProfile("Tigist Alemu", 28, 55.0, 12.0, 0.95, "high"),
        PatientProfile("Dawit Bekele", 52, 90.0, 16.0, 1.05, "low"),
    ]

    for p in patients:
        baseline = calc.calculate(p)
        print(baseline.summary())
        print()
