"""Rigorous accuracy and uncertainty metrics for SOH estimation.

Implements point accuracy (RMSE, MAE, MaxError, 95th-pct, R2) and prediction interval
quality metrics: Prediction Interval Coverage Probability (PICP), Mean Prediction
Interval Width (MPIW), and Winkler interval scores.
"""

from dataclasses import dataclass
from typing import Dict, Sequence
import numpy as np


@dataclass
class SohEvaluationMetrics:
    """Consolidated accuracy and uncertainty evaluation metrics."""

    rmse: float
    mae: float
    max_error: float
    percentile_95_error: float
    r2: float
    picp_95: float
    mpiw_95: float
    winkler_score_95: float
    sample_count: int

    def to_dict(self) -> Dict[str, float]:
        return {
            "rmse": self.rmse,
            "mae": self.mae,
            "max_error": self.max_error,
            "percentile_95_error": self.percentile_95_error,
            "r2": self.r2,
            "picp_95": self.picp_95,
            "mpiw_95": self.mpiw_95,
            "winkler_score_95": self.winkler_score_95,
            "sample_count": float(self.sample_count),
        }


def compute_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root Mean Squared Error."""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def compute_mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Error."""
    return float(np.mean(np.abs(y_true - y_pred)))


def compute_max_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Maximum absolute error."""
    return float(np.max(np.abs(y_true - y_pred)))


def compute_percentile_error(y_true: np.ndarray, y_pred: np.ndarray, q: float = 95.0) -> float:
    """q-th percentile absolute error."""
    return float(np.percentile(np.abs(y_true - y_pred), q))


def compute_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Coefficient of determination R^2."""
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot <= 1e-12:
        return 1.0 if ss_res <= 1e-12 else 0.0
    return float(1.0 - (ss_res / ss_tot))


def compute_picp(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Prediction Interval Coverage Probability: fraction of y_true in [lower, upper]."""
    covered = (y_true >= lower) & (y_true <= upper)
    return float(np.mean(covered))


def compute_mpiw(lower: np.ndarray, upper: np.ndarray) -> float:
    """Mean Prediction Interval Width: average width of [lower, upper]."""
    return float(np.mean(upper - lower))


def compute_winkler_score(
    y_true: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    alpha: float = 0.05,
) -> float:
    """Standard Winkler interval score for nominal (1 - alpha) interval.
    
    Penalizes wide intervals and heavily penalizes missed ground truth:
        Score_i = (U_i - L_i) + (2/alpha)*(L_i - y_i)*1(y_i < L_i) + (2/alpha)*(y_i - U_i)*1(y_i > U_i)
    Lower score indicates a better, more calibrated and sharper prediction interval.
    """
    width = upper - lower
    under = np.maximum(0.0, lower - y_true)
    over = np.maximum(0.0, y_true - upper)
    penalty_factor = 2.0 / alpha
    scores = width + penalty_factor * under + penalty_factor * over
    return float(np.mean(scores))


def evaluate_soh_predictions(
    y_true: Sequence[float],
    y_pred: Sequence[float],
    lower_95: Sequence[float],
    upper_95: Sequence[float],
) -> SohEvaluationMetrics:
    """Evaluate comprehensive accuracy and uncertainty metrics for SOH predictions."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    lb = np.asarray(lower_95, dtype=float)
    ub = np.asarray(upper_95, dtype=float)

    if len(yt) == 0:
        raise ValueError("Cannot compute metrics on empty arrays.")

    return SohEvaluationMetrics(
        rmse=compute_rmse(yt, yp),
        mae=compute_mae(yt, yp),
        max_error=compute_max_error(yt, yp),
        percentile_95_error=compute_percentile_error(yt, yp, 95.0),
        r2=compute_r2(yt, yp),
        picp_95=compute_picp(yt, lb, ub),
        mpiw_95=compute_mpiw(lb, ub),
        winkler_score_95=compute_winkler_score(yt, lb, ub, alpha=0.05),
        sample_count=len(yt),
    )
