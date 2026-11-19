"""Python-vs-C golden-vector parity test for Pulse ElasticNet SOH estimator."""

import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import numpy as np
import pytest

from soh.embedded.pipeline import EmbeddedSohEdgePipeline

PARITY_FP32_TOLERANCE = 1e-5


def test_pulse_elasticnet_python_vs_c_golden_vector_parity(tmp_path):
    """Verify that Python embedded pipeline math and C edge implementation produce identical outputs."""
    compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
    if compiler is None:
        pytest.skip("Neither gcc nor clang is installed; skipping C parity test.")

    edge_pkg_dir = Path(__file__).resolve().parents[2] / "deliverable" / "edge_pkg"
    c_source = edge_pkg_dir / "soh_pulse_elasticnet.c"
    
    assert c_source.exists(), f"C source file missing: {c_source}"

    # Build shared library in tmp_path
    so_path = tmp_path / "libsoh_pulse_test.so"
    cmd = [
        compiler,
        "-std=c99",
        "-O2",
        "-shared",
        "-fPIC",
        "-I", str(edge_pkg_dir),
        str(c_source),
        "-o", str(so_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Compilation failed: {res.stderr}"

    # Load C shared library via ctypes
    c_lib = ctypes.CDLL(str(so_path))

    class SohEstimateC(ctypes.Structure):
        _fields_ = [
            ("soh_c", ctypes.c_float),
            ("soh_r", ctypes.c_float),
            ("variance_c", ctypes.c_float),
            ("variance_r", ctypes.c_float),
            ("status", ctypes.c_int),
            ("qual_c", ctypes.c_int),
            ("qual_r", ctypes.c_int),
        ]

    c_predict = c_lib.soh_pulse_elasticnet_predict
    c_predict.argtypes = [
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(SohEstimateC),
    ]
    c_predict.restype = None

    # Test vectors
    test_vectors = [
        np.array([0.0150, 0.0050, 1000.0, 0.0060, 4000.0, 0.0260, 5.0, 25.0, -2.0, 25.0, 3.30], dtype=np.float32), # At mean
        np.array([0.0155, 0.0052, 980.0, 0.0062, 3950.0, 0.0269, 5.1, 24.5, -2.0, 25.0, 3.32], dtype=np.float32),  # Nominal pulse
        np.array([0.0250, 0.0100, 500.0, 0.0150, 2000.0, 0.0500, 8.0, 40.0, -1.0, 15.0, 3.10], dtype=np.float32),  # Aged cold pulse
        np.array([0.0080, 0.0020, 1500.0, 0.0030, 6000.0, 0.0120, 3.0, 15.0, -3.0, 45.0, 3.45], dtype=np.float32), # Fresh warm pulse
    ]

    pipeline = EmbeddedSohEdgePipeline()

    for idx, vec in enumerate(test_vectors):
        # 1. Python prediction
        py_est = pipeline.predict_pulse(vec)

        # 2. C prediction
        c_raw = (ctypes.c_float * 11)(*vec.tolist())
        c_est = SohEstimateC()
        c_predict(c_raw, ctypes.byref(c_est))

        # Check numerical agreement to single-precision float accuracy (PARITY_FP32_TOLERANCE)
        assert abs(float(py_est.soh_c) - float(c_est.soh_c)) <= PARITY_FP32_TOLERANCE, (
            f"Vector {idx} SOH_C mismatch: Python={py_est.soh_c}, C={c_est.soh_c}"
        )
        assert abs(float(py_est.soh_r) - float(c_est.soh_r)) <= PARITY_FP32_TOLERANCE, (
            f"Vector {idx} SOH_R mismatch: Python={py_est.soh_r}, C={c_est.soh_r}"
        )
        # Qualification in C must be UNQUALIFIED (0)
        assert c_est.qual_c == 0, "C edge qual_c must default to UNQUALIFIED (0)"
        assert c_est.qual_r == 0, "C edge qual_r must default to UNQUALIFIED (0)"


def test_soh_pulse_v2_python_vs_c_parity(tmp_path):
    """Verify numerical parity between Python trained v2 model and auto-generated C header."""
    compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
    if compiler is None:
        pytest.skip("Neither gcc nor clang is installed; skipping C parity test.")

    header_file = Path(__file__).resolve().parents[2] / "deliverable" / "edge_pkg" / "soh_pulse_elasticnet_v2.h"
    assert header_file.exists(), f"Auto-generated V2 C header missing: {header_file}"

    # Write small C wrapper exposing soh_predict_pulse
    c_wrapper = tmp_path / "wrapper_v2.c"
    c_wrapper.write_text(f"""
#include "{header_file}"

void test_predict_v2(const float in[11], float* c, float* r) {{
    soh_predict_pulse(in, c, r);
}}
""")

    so_path = tmp_path / "libsoh_pulse_v2.so"
    cmd = [
        compiler,
        "-std=c99",
        "-O2",
        "-shared",
        "-fPIC",
        "-I", str(header_file.parent),
        str(c_wrapper),
        "-o", str(so_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Compilation failed: {res.stderr}"

    c_lib = ctypes.CDLL(str(so_path))
    c_predict_v2 = c_lib.test_predict_v2
    c_predict_v2.argtypes = [
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
    ]
    c_predict_v2.restype = None

    # Load calibration parameters from deliverable/calibrations/uconn_soh_pulse_v2.json
    calib_path = Path(__file__).resolve().parents[2] / "deliverable" / "calibrations" / "uconn_soh_pulse_v2.json"
    import json
    with open(calib_path, "r", encoding="utf-8") as f:
        calib = json.load(f)

    # Qualification check: must be UNQUALIFIED for 100 Ah target
    assert calib["qualification_status"] == "UNQUALIFIED"

    means = np.array(calib["scaler"]["mean"][:11], dtype=np.float32)
    scales = np.array(calib["scaler"]["scale"][:11], dtype=np.float32)
    coefs_c = np.array(calib["soh_c"]["coefficients"][:11], dtype=np.float32)
    intercept_c = np.float32(calib["soh_c"]["intercept"])
    coefs_r = np.array(calib["soh_r"]["coefficients"][:11], dtype=np.float32)
    intercept_r = np.float32(calib["soh_r"]["intercept"])

    # Test vectors
    test_vectors = [
        means,  # Exactly at scaler mean -> should return intercept
        means + scales,  # 1 sigma above mean
        means - 0.5 * scales,  # 0.5 sigma below mean
        np.array([0.018, 0.010, 550.0, 0.065, 1400.0, 0.093, 5.5, 93.0, 0.45, 25.0, 3.31], dtype=np.float32),
        np.array([0.025, 0.015, 400.0, 0.080, 1100.0, 0.120, 7.0, 110.0, 0.45, 25.0, 3.28], dtype=np.float32),
    ]

    for idx, vec in enumerate(test_vectors):
        # Python prediction
        x_norm = (vec - means) / scales
        py_c = float(intercept_c + np.dot(coefs_c, x_norm))
        py_r = float(intercept_r + np.dot(coefs_r, x_norm))

        # C prediction
        c_raw = (ctypes.c_float * 11)(*vec.tolist())
        c_val_c = ctypes.c_float()
        c_val_r = ctypes.c_float()
        c_predict_v2(c_raw, ctypes.byref(c_val_c), ctypes.byref(c_val_r))

        assert abs(py_c - c_val_c.value) <= PARITY_FP32_TOLERANCE, (
            f"V2 vector {idx} SOH_C mismatch: Py={py_c}, C={c_val_c.value}"
        )
        assert abs(py_r - c_val_r.value) <= PARITY_FP32_TOLERANCE, (
            f"V2 vector {idx} SOH_R mismatch: Py={py_r}, C={c_val_r.value}"
        )
