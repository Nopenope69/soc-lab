"""SOH estimation algorithms and common interfaces."""

from soh.estimators.base import SohEstimator, SupportsEmbeddedExport
from soh.estimators.constant_mean import ConstantMeanEstimator
from soh.estimators.knee_point_monitor import KneePointMonitor, RegimeMonitorAlert, RegimeStatus

try:
    from soh.estimators.baseline_ridge import BaselineRidgeEstimator
except ImportError:
    BaselineRidgeEstimator = None

try:
    from soh.estimators.gru import GruSohEstimator
except ImportError:
    GruSohEstimator = None

try:
    from soh.estimators.ica_gpr_ekf import IcaGprEkfEstimator
except ImportError:
    IcaGprEkfEstimator = None

try:
    from soh.estimators.pulse_elastic_net import PulseElasticNetEstimator
except ImportError:
    PulseElasticNetEstimator = None

__all__ = [
    "BaselineRidgeEstimator",
    "ConstantMeanEstimator",
    "GruSohEstimator",
    "IcaGprEkfEstimator",
    "KneePointMonitor",
    "PulseElasticNetEstimator",
    "RegimeMonitorAlert",
    "RegimeStatus",
    "SohEstimator",
    "SupportsEmbeddedExport",
]
