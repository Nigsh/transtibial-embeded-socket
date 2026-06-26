"""
SmartFit | analysis_engine.py
==============================
Stage 3 + 4 — Deviation analysis, Fit Quality Score, and adjustment
recommendation engine.

Compares ideal pressure baseline (Stage 1) against FSR sensor readings
(Stage 2), then:
  • Classifies each sensor zone (optimal / elevated / hotspot / low)
  • Computes Fit Quality Score 0–100 (FR2)
  • Generates clinical adjustment recommendations (FR3)
  • Prepares heatmap data for the UI

Run standalone for a full analysis report:
    python analysis_engine.py
"""

from __future__ import annotations
import dataclasses
from typing import List, Dict, Optional
from fsr_sensor import FaultType, SensorFrame
from pressure_calculator import PressureBaseline, SENSORS, SensorSpec


# ---------------------------------------------------------------------------
# Pressure thresholds (ratio vs. ideal baseline)
# Based on Graser et al. (2020) DTI risk literature
# ---------------------------------------------------------------------------

THRESHOLD_LOW            = 0.80   # below → under-loaded / slack
THRESHOLD_OPTIMAL_HIGH   = 1.20   # above → elevated
THRESHOLD_HOTSPOT        = 1.50   # above → hotspot / DTI risk


# ---------------------------------------------------------------------------
# Zone status
# ---------------------------------------------------------------------------

STATUS_OPTIMAL  = "optimal"
STATUS_ELEVATED = "elevated"
STATUS_HOTSPOT  = "hotspot"
STATUS_LOW      = "low"

STATUS_COLORS = {
    STATUS_OPTIMAL:  "#22c55e",   # green
    STATUS_ELEVATED: "#f59e0b",   # yellow/amber
    STATUS_HOTSPOT:  "#ef4444",   # red
    STATUS_LOW:      "#3b82f6",   # blue
}


def classify_ratio(ratio: float) -> str:
    if ratio > THRESHOLD_HOTSPOT:
        return STATUS_HOTSPOT
    if ratio > THRESHOLD_OPTIMAL_HIGH:
        return STATUS_ELEVATED
    if ratio < THRESHOLD_LOW:
        return STATUS_LOW
    return STATUS_OPTIMAL


# ---------------------------------------------------------------------------
# Per-sensor analysis result
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class SensorAnalysis:
    sensor: SensorSpec
    ideal_kpa: float
    measured_kpa: float
    ratio: float
    status: str
    color: str
    deviation_pct: float    # signed % deviation from ideal

    @property
    def is_critical(self) -> bool:
        return self.status == STATUS_HOTSPOT

    def to_dict(self) -> Dict:
        return {
            "id": self.sensor.id,
            "name": self.sensor.name,
            "zone": self.sensor.zone,
            "ideal_kpa": round(self.ideal_kpa, 2),
            "measured_kpa": round(self.measured_kpa, 2),
            "ratio": round(self.ratio, 3),
            "status": self.status,
            "color": self.color,
            "deviation_pct": round(self.deviation_pct, 1),
            "canvas_x": self.sensor.canvas_x,
            "canvas_y": self.sensor.canvas_y,
        }


# ---------------------------------------------------------------------------
# Adjustment recommendation
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Recommendation:
    severity: str         # "critical" | "warning" | "info" | "ok"
    zone: str
    text: str
    action: str           # short action label for UI

    def to_dict(self) -> Dict:
        return dataclasses.asdict(self)


# Recommendation rule database (mirrors TF-Lite decision tree, Section 8.3)
RECOMMENDATION_RULES: Dict[FaultType, List[Recommendation]] = {
    FaultType.NONE: [
        Recommendation("ok", "all", "Fit is within target range.", "No action needed"),
    ],
    FaultType.TIBIA: [
        Recommendation("critical", "anterior", "Anterior tibia crest over-loaded. Risk of skin breakdown.", "Add 3 mm anterior pad"),
        Recommendation("warning",  "anterior", "Proximal trim line may be too high.", "Lower anterior trim line 2–3 mm"),
    ],
    FaultType.DISTAL: [
        Recommendation("critical", "distal",   "Distal end-bearing pad over-loaded. DTI risk.", "Add 5 mm distal relief pad"),
        Recommendation("warning",  "proximal", "Excessive pistoning may be loading distal end.", "Check suspension — re-tighten liner"),
    ],
    FaultType.MEDIAL: [
        Recommendation("critical", "medial",   "Medial tibial flare bony prominence over-loaded.", "Relieve medial wall 2–3 mm"),
        Recommendation("info",     "lateral",  "Lateral zone under-loaded — possible socket tilt.", "Check coronal alignment"),
    ],
    FaultType.POSTERIOR: [
        Recommendation("warning",  "posterior","Posterior calf region under-loaded — suspension slack.", "Tighten posterior straps 2–3 mm"),
        Recommendation("info",     "posterior","Posterior slack may cause gait asymmetry.", "Re-check BK pylon alignment"),
    ],
    FaultType.MULTI: [
        Recommendation("critical", "anterior", "Anterior tibia crest critically over-loaded.", "Add 3 mm anterior pad immediately"),
        Recommendation("critical", "distal",   "Distal end over-loaded.", "Add 4 mm distal relief pad"),
        Recommendation("warning",  "lateral",  "Lateral mid-shaft abnormal.", "Re-seat liner; re-check lateral wall"),
        Recommendation("info",     "posterior","Posterior region under-loaded.", "Tighten suspension 2 mm"),
    ],
}


# ---------------------------------------------------------------------------
# Full analysis result
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class AnalysisResult:
    patient_name: str
    sensors: List[SensorAnalysis]
    fit_quality_score: int       # 0–100
    hotspot_count: int
    low_count: int
    peak_pressure_kpa: float
    recommendations: List[Recommendation]
    fault: FaultType             # known fault (simulation) or NONE (live)

    @property
    def status_label(self) -> str:
        if self.fit_quality_score >= 80:
            return "Good Fit"
        if self.fit_quality_score >= 60:
            return "Needs Adjustment"
        return "Poor Fit"

    @property
    def status_color(self) -> str:
        if self.fit_quality_score >= 80:
            return "#22c55e"
        if self.fit_quality_score >= 60:
            return "#f59e0b"
        return "#ef4444"

    def summary(self) -> str:
        lines = [
            "=" * 65,
            f"  Analysis Report — {self.patient_name}",
            "=" * 65,
            f"  Fit Quality Score:  {self.fit_quality_score}/100  ({self.status_label})",
            f"  Peak pressure:      {self.peak_pressure_kpa:.1f} kPa",
            f"  Hotspot zones:      {self.hotspot_count}",
            f"  Low-load zones:     {self.low_count}",
            "",
            f"  {'#':<3} {'Sensor':<35} {'Ideal':>7} {'Meas.':>7} {'Ratio':>6}  Status",
            "  " + "-" * 65,
        ]
        for sa in self.sensors:
            icon = {"hotspot":"[!]","elevated":"[~]","low":"[↓]","optimal":"[✓]"}.get(sa.status,"[-]")
            lines.append(
                f"  {sa.sensor.id:<3} {sa.sensor.name:<35} "
                f"{sa.ideal_kpa:>6.1f}  {sa.measured_kpa:>6.1f}  {sa.ratio:>5.2f}  {icon} {sa.status}"
            )
        lines += ["", "  Recommendations:"]
        for r in self.recommendations:
            icon = {"critical":"[!!!]","warning":"[!] ","info":"[i] ","ok":"[✓] "}.get(r.severity,"[-]")
            lines.append(f"  {icon} {r.text}")
            lines.append(f"       → {r.action}")
        lines.append("=" * 65)
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "patient_name": self.patient_name,
            "fit_quality_score": self.fit_quality_score,
            "status_label": self.status_label,
            "status_color": self.status_color,
            "peak_pressure_kpa": round(self.peak_pressure_kpa, 2),
            "hotspot_count": self.hotspot_count,
            "low_count": self.low_count,
            "sensors": [s.to_dict() for s in self.sensors],
            "recommendations": [r.to_dict() for r in self.recommendations],
        }


# ---------------------------------------------------------------------------
# Analysis engine
# ---------------------------------------------------------------------------

class AnalysisEngine:
    """
    Compares a SensorFrame against the ideal PressureBaseline and
    produces an AnalysisResult with FQS, heatmap data, and recommendations.
    """

    @staticmethod
    def _fit_quality_score(sensor_analyses: List[SensorAnalysis]) -> int:
        """
        Score each sensor 0–1 based on deviation from ideal,
        average, scale to 0–100. Penalty: linear ramp, 0.67 deviation = 0.
        Tuned so ±10% noise (NFR1) yields FQS ≥ 85.
        """
        scores = [
            max(0.0, 1.0 - abs(sa.ratio - 1.0) * 1.5)
            for sa in sensor_analyses
            if sa.ideal_kpa > 0
        ]
        return int(round(sum(scores) / len(scores) * 100)) if scores else 0

    def analyze(
        self,
        baseline: PressureBaseline,
        frame: SensorFrame,
        fault: FaultType = FaultType.NONE,
    ) -> AnalysisResult:
        """
        Run full analysis pipeline.

        Parameters
        ----------
        baseline  : from PressureCalculator
        frame     : from SimulatedFSR or BleFSR
        fault     : known fault type (simulation) — use NONE for live data
        """
        sensor_analyses = []
        for s in SENSORS:
            ideal   = baseline.ideal_kpa[s.id]
            meas    = frame.pressure_kpa[s.id]
            ratio   = meas / ideal if ideal > 0 else 0.0
            status  = classify_ratio(ratio)
            dev_pct = (ratio - 1.0) * 100.0
            sensor_analyses.append(SensorAnalysis(
                sensor=s,
                ideal_kpa=ideal,
                measured_kpa=meas,
                ratio=ratio,
                status=status,
                color=STATUS_COLORS[status],
                deviation_pct=dev_pct,
            ))

        fqs         = self._fit_quality_score(sensor_analyses)
        hotspots    = sum(1 for sa in sensor_analyses if sa.status == STATUS_HOTSPOT)
        low_count   = sum(1 for sa in sensor_analyses if sa.status == STATUS_LOW)
        peak        = max(sa.measured_kpa for sa in sensor_analyses)
        recs        = RECOMMENDATION_RULES.get(fault, RECOMMENDATION_RULES[FaultType.NONE])

        # Dynamic override: flag unexpected hotspots when fault=NONE
        if fault == FaultType.NONE and hotspots > 0:
            recs = [
                Recommendation(
                    "critical", sa.sensor.zone,
                    f"Unexpected hotspot at {sa.sensor.name}.",
                    "Recheck sensor placement and socket fit"
                )
                for sa in sensor_analyses if sa.is_critical
            ]

        return AnalysisResult(
            patient_name=baseline.patient.name,
            sensors=sensor_analyses,
            fit_quality_score=fqs,
            hotspot_count=hotspots,
            low_count=low_count,
            peak_pressure_kpa=peak,
            recommendations=recs,
            fault=fault,
        )


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pressure_calculator import PressureCalculator, PatientProfile
    from fsr_sensor import SimulatedFSR, FaultType

    calc    = PressureCalculator()
    engine  = AnalysisEngine()

    cases = [
        ("Abebe Girma",  70, 14, 1.00, "moderate", FaultType.NONE),
        ("Tigist Alemu", 55, 12, 0.95, "high",     FaultType.TIBIA),
        ("Dawit Bekele", 90, 10, 1.05, "low",      FaultType.MULTI),
    ]

    for name, w, l, t, act, fault in cases:
        patient  = PatientProfile(name, 35, w, l, t, act)
        baseline = calc.calculate(patient)
        fsr      = SimulatedFSR(baseline.ideal_kpa, fault=fault, noise=0.05, seed=42)
        frame    = fsr.averaged_frame(n_samples=10)
        result   = engine.analyze(baseline, frame, fault=fault)
        print(result.summary())
        print()
