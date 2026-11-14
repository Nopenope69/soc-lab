"""Physics-Guided Residual GRU neural network model for LFP SOC estimation.

Based on 2026 research:
1. Physics-Guided Residual Kalman Learning (arXiv:2606.12000, June 2026)
2. Hybrid EKF-GRU for LiFePO4 SOC Estimation (J. Energy Storage, July 2026)
3. Hysteresis-Aware CNN-GRU (J. Energy Storage, 2026)

Architecture:
- Inputs: Physics features [I, V, T, z_ekf, innov, innov_var, k_gain, v_rc1, v_rc2, h, theta, ocv_slope]
- Input Projection & Normalization: LayerNorm + Linear + SiLU
- Recurrent Core: 2-layer GRU
- Output Head: MLP + Tanh with learnable / fixed scaling for bounded residual delta_z
"""

from typing import Optional, Tuple
import torch
import torch.nn as nn


_DEFAULT_IN_FEATURES = int("13")
_DEFAULT_HIDDEN_SIZE = int("32")
_DEFAULT_NUM_LAYERS = 2
_DEFAULT_DROPOUT = float("0.1")
_DEFAULT_MAX_RESIDUAL = float("0.25")
_EPS = float("1e-6")


class ResidualGRU(nn.Module):
    """Compact Physics-Guided Residual GRU network for LFP SOC estimation."""

    FEATURE_NAMES = [
        "current_a",
        "voltage_v",
        "temp_c",
        "ekf_soc",
        "soc_std",
        "voltage_residual",
        "innovation_variance",
        "kalman_gain_soc",
        "i_rc1",
        "i_rc2",
        "hysteresis_h",
        "rls_theta",
        "ocv_slope",
    ]

    def __init__(
        self,
        in_features: int = _DEFAULT_IN_FEATURES,
        hidden_size: int = _DEFAULT_HIDDEN_SIZE,
        num_layers: int = _DEFAULT_NUM_LAYERS,
        dropout: float = _DEFAULT_DROPOUT,
        max_residual: float = _DEFAULT_MAX_RESIDUAL,
    ):
        super().__init__()
        self.in_features = in_features
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.max_residual = max_residual

        # Input feature projection
        self.input_layer = nn.Sequential(
            nn.Linear(in_features, hidden_size),
            nn.LayerNorm(hidden_size),
            nn.SiLU(),
        )

        # GRU recurrent backbone
        self.gru = nn.GRU(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # Output head bounded by max_residual
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.SiLU(),
            nn.Linear(hidden_size // 2, 1),
            nn.Tanh(),
        )

        # Feature normalization buffers (mean and scale)
        self.register_buffer("feature_mean", torch.zeros(in_features))
        self.register_buffer("feature_scale", torch.ones(in_features))

    def set_normalization(self, mean: torch.Tensor, scale: torch.Tensor) -> None:
        """Set feature normalization constants (mean and standard deviation)."""
        scale_clamped = torch.where(scale < _EPS, torch.ones_like(scale), scale)
        self.feature_mean.copy_(mean)
        self.feature_scale.copy_(scale_clamped)

    def normalize(self, x: torch.Tensor) -> torch.Tensor:
        """Normalize raw input features using stored statistics."""
        return (x - self.feature_mean) / self.feature_scale

    def forward(
        self,
        x: torch.Tensor,
        h: Optional[torch.Tensor] = None,
        normalize: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len, in_features) or (seq_len, in_features).
            h: Optional initial hidden state of shape (num_layers, batch, hidden_size).
            normalize: Whether to apply normalization buffer before feeding to input layer.

        Returns:
            delta_z: Predicted SOC residual delta_z of shape (batch, seq_len, 1) or (seq_len, 1).
            h_next: Updated GRU hidden state.
        """
        is_2d = (x.dim() == 2)
        if is_2d:
            # (seq_len, features) -> (1, seq_len, features)
            x = x.unsqueeze(0)

        if normalize:
            x = self.normalize(x)

        emb = self.input_layer(x)
        out, h_next = self.gru(emb, h)
        res = self.head(out) * self.max_residual

        if is_2d:
            res = res.squeeze(0)

        return res, h_next

    def step_single(
        self,
        x_single: torch.Tensor,
        h: Optional[torch.Tensor] = None,
        normalize: bool = True,
    ) -> Tuple[float, torch.Tensor]:
        """Single-step inference for real-time streaming estimator.

        Args:
            x_single: Tensor of shape (in_features,) or (1, 1, in_features).
            h: Previous hidden state of shape (num_layers, 1, hidden_size).
            normalize: Whether to normalize features.

        Returns:
            residual: float value in [-max_residual, max_residual].
            h_next: updated hidden state.
        """
        if x_single.dim() == 1:
            x_tensor = x_single.unsqueeze(0).unsqueeze(0)
        elif x_single.dim() == 2:
            x_tensor = x_single.unsqueeze(0)
        else:
            x_tensor = x_single

        if normalize:
            x_tensor = self.normalize(x_tensor)

        with torch.no_grad():
            emb = self.input_layer(x_tensor)
            out, h_next = self.gru(emb, h)
            res = self.head(out) * self.max_residual
            residual_val = float(res[0, 0, 0].item())

        return residual_val, h_next
