"""Physics-Informed Neural Network (PINN) battery degradation modeling package."""

from soh.models.pinn.diagnostics import (
    ExtrapolationResult,
    GradientEpochRecord,
    KineticMismatchResult,
    PhysicsWeightSweepResult,
    PinnDiagnosticHistory,
    record_loss_and_gradient_diagnostics,
    run_kinetic_mismatch_benchmark,
    run_long_horizon_extrapolation,
    run_nonlinear_stage_benchmark,
    run_temperature_transfer_benchmark,
    sweep_physics_weights_multiseed,
)
from soh.models.pinn.estimator import (
    PinnSohEstimator,
    PinnTrainingConfig,
)
from soh.models.pinn.losses import (
    LossWeights,
    PinnLossFunction,
)
from soh.models.pinn.network import (
    BatteryDegradationPINN,
    NetworkConfig,
)
from soh.models.pinn.sei_kinetics import (
    LithiumPlatingModule,
    LithiumPlatingParameters,
    LossOfActiveMaterialModule,
    LamParameters,
    SeiKineticsParameters,
    SeiKineticsPhysics,
)

__all__ = [
    "BatteryDegradationPINN",
    "NetworkConfig",
    "PinnLossFunction",
    "LossWeights",
    "PinnSohEstimator",
    "PinnTrainingConfig",
    "SeiKineticsParameters",
    "SeiKineticsPhysics",
    "LithiumPlatingModule",
    "LithiumPlatingParameters",
    "LossOfActiveMaterialModule",
    "LamParameters",
    "GradientEpochRecord",
    "PinnDiagnosticHistory",
    "PhysicsWeightSweepResult",
    "ExtrapolationResult",
    "KineticMismatchResult",
    "record_loss_and_gradient_diagnostics",
    "sweep_physics_weights_multiseed",
    "run_long_horizon_extrapolation",
    "run_nonlinear_stage_benchmark",
    "run_kinetic_mismatch_benchmark",
    "run_temperature_transfer_benchmark",
]
