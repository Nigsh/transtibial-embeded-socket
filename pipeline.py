"""
SmartFit | pipeline.py
=======================
Main pipeline — ties all 4 stages together and serves the UI.

Pipeline stages:
  1. pressure_calculator.py  — ideal pressure baseline from patient data
  2. fsr_sensor.py           — FSR sensor readings (simulated or live BLE)
  3. analysis_engine.py      — deviation analysis + FQS + recommendations
  4. app.py (UI)             — Flask web server + heatmap dashboard

Usage
-----
    # Run full pipeline (headless, prints report):
    python pipeline.py

    # Start the web UI:
    python app.py

    # Or run the full demo with all fault cases:
    python pipeline.py --demo
"""

import json
import argparse
import dataclasses
from pressure_calculator import PressureCalculator, PatientProfile
from fsr_sensor import SimulatedFSR, FaultType
from analysis_engine import AnalysisEngine, AnalysisResult


class SmartFitPipeline:
    """
    Orchestrates the full SmartFit measurement pipeline.

    Parameters
    ----------
    patient  : PatientProfile with validated anthropometric data
    fault    : FaultType for simulation (use NONE for live BLE data)
    noise    : FSR noise level (0.05 = ±10%, matches NFR1)
    seed     : random seed for reproducibility
    """

    def __init__(
        self,
        patient: PatientProfile,
        fault: FaultType = FaultType.NONE,
        noise: float = 0.05,
        seed: int = None,
    ):
        self.patient  = patient
        self.fault    = fault
        self.noise    = noise
        self.seed     = seed

        self._calc    = PressureCalculator()
        self._engine  = AnalysisEngine()

    def run(self, n_samples: int = 10) -> AnalysisResult:
        """
        Execute all pipeline stages and return AnalysisResult.

        Parameters
        ----------
        n_samples : number of FSR frames to average (10 Hz → 1 s window)
        """
        # Stage 1 — Ideal pressure baseline
        baseline = self._calc.calculate(self.patient)

        # Stage 2 — FSR sensor readings
        fsr   = SimulatedFSR(
            ideal_kpa=baseline.ideal_kpa,
            fault=self.fault,
            noise=self.noise,
            seed=self.seed,
        )
        frame = fsr.averaged_frame(n_samples=n_samples)

        # Stage 3+4 — Analysis + recommendations
        result = self._engine.analyze(baseline, frame, fault=self.fault)
        return result

    def run_to_json(self, n_samples: int = 10) -> str:
        """Run pipeline and return JSON string (for API / BLE response)."""
        result = self.run(n_samples=n_samples)
        return json.dumps(result.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SmartFit Pipeline")
    parser.add_argument("--demo",   action="store_true", help="Run all fault cases")
    parser.add_argument("--weight", type=float, default=70.0)
    parser.add_argument("--length", type=float, default=14.0)
    parser.add_argument("--tight",  type=float, default=1.0)
    parser.add_argument("--fault",  type=str,   default="none",
                        choices=[f.value for f in FaultType])
    parser.add_argument("--name",   type=str,   default="Patient")
    args = parser.parse_args()

    if args.demo:
        demo_cases = [
            ("Abebe Girma",  70, 14, 1.00, "moderate", FaultType.NONE),
            ("Tigist Alemu", 55, 12, 0.95, "high",     FaultType.TIBIA),
            ("Dawit Bekele", 90, 10, 1.05, "low",      FaultType.DISTAL),
            ("Marta Hailu",  65, 16, 1.10, "moderate", FaultType.MEDIAL),
            ("Yonas Tesfaye",85, 11, 1.00, "moderate", FaultType.MULTI),
        ]
        for name, w, l, t, act, fault in demo_cases:
            patient  = PatientProfile(name, 35, w, l, t, act)
            pipeline = SmartFitPipeline(patient, fault=fault, noise=0.05, seed=42)
            result   = pipeline.run()
            print(result.summary())
            print()
    else:
        patient  = PatientProfile(
            args.name, 35,
            args.weight, args.length, args.tight, "moderate"
        )
        pipeline = SmartFitPipeline(
            patient,
            fault=FaultType(args.fault),
            noise=0.05,
            seed=42,
        )
        result = pipeline.run()
        print(result.summary())


if __name__ == "__main__":
    main()
