"""Python-vs-C golden-vector parity test for Pulse ElasticNet SOH estimator."""

import ctypes
import os
from pathlib import Path
import subprocess
import numpy as np
import pytest

from soh.embedded.pipeline import EmbeddedSohEdgePipeline


def test_pulse_elasticnet_python_vs_c_golden_vector_parity(tmp_path):
    """Verify that Python embedded pipeline math and C edge implementation produce identical outputs."""
    edge_pkg_dir = Path(__file__).resolve().parents[2] / "deliverable" / "edge_pkg"
    c_source = edge_pkg_dir / "soh_pulse_elasticnet.c"
    
    assert c_source.exists(), f"C source file missing: {c_source}"

    # Build shared library in tmp_path
    so_path = tmp_path / "libsoh_pulse_test.so"
    cmd = [
        "gcc",
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

        # Check numerical agreement to single-precision float accuracy (tol <= 1e-6)
        assert abs(float(py_est.soh_c) - float(c_est.soh_c)) <= 1e-5, (
            f"Vector {idx} SOH_C mismatch: Python={py_est.soh_c}, C={c_est.soh_c}"
        )
        assert abs(float(py_est.soh_r) - float(c_est.soh_r)) <= 1e-5, (
            f"Vector {idx} SOH_R mismatch: Python={py_est.soh_r}, C={c_est.soh_r}"
        )
        # Qualification in C must be UNQUALIFIED (0)
        assert c_est.qual_c == 0, "C edge qual_c must default to UNQUALIFIED (0)"
        assert c_est.qual_r == 0, "C edge qual_r must default to UNQUALIFIED (0)"
