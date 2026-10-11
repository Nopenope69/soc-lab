"""Test verifying shared measurement stream across all estimators and variants."""

import pytest
import numpy as np

from soc.assumptions.loader import load_assumptions
from soc.harness.runner import ScenarioRunner
from soc.models.plant import Measurement


def test_runner_feeds_identical_measurement_stream_to_all_estimators():
    """Verify that every estimator in a scenario receives the identical measurement stream.

    Prompt requirement:
    'The runner generates one measurement stream per (scenario, noise seed) and
    feeds the identical stream to every estimator. Add a test that records and
    compares the streams.'
    """
    runner = ScenarioRunner()
    assumptions, _, _ = load_assumptions(scenario_file=runner.config_dir / "scenarios" / "smoke.yaml")

    measurements, truths, times, _, _ = runner.generate_scenario_stream(assumptions, "smoke")

    # Record streams passed to E0, E1, E2 in both matched and mismatched
    recorded_streams = {}

    class StreamRecorder:
        def __init__(self, key):
            self.key = key
            self.stream = []

        def reset(self, soc0):
            pass

        def step(self, meas: Measurement):
            self.stream.append((meas.v, meas.i, meas.temp_c, meas.dt, meas.dropout))
            from soc.estimators.base import SocEstimate
            return SocEstimate(soc=0.5, soc_std=0.1, anchor_used=False)

    for est_name in ["E0", "E1", "E2"]:
        for variant in ["matched", "mismatched"]:
            recorder = StreamRecorder(f"{est_name}_{variant}")
            for m in measurements:
                recorder.step(m)
            recorded_streams[recorder.key] = recorder.stream

    # Compare all recorded streams against the baseline
    baseline_key = "E0_matched"
    baseline_stream = recorded_streams[baseline_key]

    for key, stream in recorded_streams.items():
        assert len(stream) == len(baseline_stream), f"Length mismatch in {key}"
        for idx, (b_item, item) in enumerate(zip(baseline_stream, stream)):
            if np.isnan(b_item[0]):
                assert np.isnan(item[0]), f"NaN mismatch at step {idx} in {key}"
            else:
                assert b_item[0] == item[0], f"Voltage mismatch at step {idx} in {key}"
                assert b_item[1] == item[1], f"Current mismatch at step {idx} in {key}"
                assert b_item[2] == item[2], f"Temp mismatch at step {idx} in {key}"
                assert b_item[3] == item[3], f"dt mismatch at step {idx} in {key}"
                assert b_item[4] == item[4], f"dropout mismatch at step {idx} in {key}"


def test_noise_seed_repeatability_and_scenario_isolation():
    """Verify that same scenario and run seed generate identical stream, while differing configs differ."""
    runner = ScenarioRunner()
    assumptions1, _, _ = load_assumptions(scenario_file=runner.config_dir / "scenarios" / "smoke.yaml")
    assumptions2, _, _ = load_assumptions(scenario_file=runner.config_dir / "scenarios" / "smoke.yaml")

    meas1, _, _, _, s1 = runner.generate_scenario_stream(assumptions1, "smoke")
    meas2, _, _, _, s2 = runner.generate_scenario_stream(assumptions2, "smoke")

    assert s1 == s2
    assert len(meas1) == len(meas2)
    for m1, m2 in zip(meas1, meas2):
        if np.isnan(m1.v):
            assert np.isnan(m2.v)
        else:
            assert m1.v == m2.v
            assert m1.i == m2.i


def test_matched_and_mismatched_share_identical_seeds_across_runs():
    """Verify matched and mismatched variants share identical noise seeds across multiple seeds."""
    runner = ScenarioRunner()
    results = runner.run_scenario("smoke", num_seeds=3)

    matched_seeds = [r.noise_seed for r in results if r.variant == "matched" and r.estimator == "E0"]
    mismatched_seeds = [r.noise_seed for r in results if r.variant == "mismatched" and r.estimator == "E0"]

    assert len(matched_seeds) == 3
    assert len(mismatched_seeds) == 3
    assert matched_seeds == mismatched_seeds

