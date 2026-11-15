"""PyTorch Neural Network architecture for Battery Degradation PINN.

Implements a multi-output neural network with smooth activations (SiLU/Tanh)
for gradient-based physical residual evaluation, heteroscedastic uncertainty heads,
and Monte Carlo Dropout support.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class NetworkConfig:
    """Hyperparameters for BatteryDegradationPINN."""

    input_dim: int = 5           # [t_s, ah_throughput, temp_k, current_a, soc]
    hidden_dims: Tuple[int, ...] = (64, 64, 32)
    dropout_rate: float = 0.05
    activation: str = "silu"     # "silu", "tanh", or "gelu"
    delta_sei_scale_nm: float = 1e-9  # Scale factor for SEI thickness (nm to meters)
    
    # Normalization constants for physical inputs [t_s, ah_throughput, temp_k, current_a, soc]
    # Scales inputs to ~[-1, 1] range while autograd directly differentiates wrt physical inputs
    input_scales: Tuple[float, ...] = (1.0e-6, 1.0e-3, 0.02, 0.4348, 1.0)
    input_shifts: Tuple[float, ...] = (0.0, 0.0, -298.15, 0.0, -0.5)


class BatteryDegradationPINN(nn.Module):
    """Physics-Informed Neural Network for multi-state battery degradation."""

    def __init__(self, config: Optional[NetworkConfig] = None):
        super().__init__()
        self.config = config or NetworkConfig()

        if self.config.activation == "tanh":
            act_fn = nn.Tanh
        elif self.config.activation == "gelu":
            act_fn = nn.GELU
        else:
            act_fn = nn.SiLU

        # Register input normalization buffers
        self.register_buffer("scales", torch.tensor(self.config.input_scales, dtype=torch.float32))
        self.register_buffer("shifts", torch.tensor(self.config.input_shifts, dtype=torch.float32))

        # Shared feature extractor trunk
        layers: List[nn.Module] = []
        prev_dim = self.config.input_dim

        for h_dim in self.config.hidden_dims:
            layers.append(nn.Linear(prev_dim, h_dim))
            layers.append(act_fn())
            if self.config.dropout_rate > 0.0:
                layers.append(nn.Dropout(p=self.config.dropout_rate))
            prev_dim = h_dim

        self.trunk = nn.Sequential(*layers)

        # Output Heads:
        # 1. SEI thickness head: output in nanometers, constrained positive via Softplus
        self.head_sei = nn.Sequential(
            nn.Linear(prev_dim, 16),
            act_fn(),
            nn.Linear(16, 1),
            nn.Softplus(),  # Ensures delta_sei > 0
        )

        # 2. SOH_C (Capacity retention) head: centered around 1.0, constrained via Sigmoid
        self.head_soh_c = nn.Sequential(
            nn.Linear(prev_dim, 16),
            act_fn(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

        # 3. SOH_R (Resistance retention) head: centered around 1.0, constrained via Sigmoid
        self.head_soh_r = nn.Sequential(
            nn.Linear(prev_dim, 16),
            act_fn(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

        # 4. Heteroscedastic log-variance heads for SOH_C and SOH_R
        self.head_log_var_c = nn.Sequential(
            nn.Linear(prev_dim, 16),
            act_fn(),
            nn.Linear(16, 1),
        )
        self.head_log_var_r = nn.Sequential(
            nn.Linear(prev_dim, 16),
            act_fn(),
            nn.Linear(16, 1),
        )

        # Initialize output biases to realistic battery domain ranges:
        # Sigmoid(3.5) ~ 0.97 for pristine SOH_C / SOH_R
        # log_var ~ -6.0 (variance ~ 0.0025, std ~ 0.05)
        nn.init.constant_(self.head_soh_c[2].bias, 3.5)
        nn.init.constant_(self.head_soh_r[2].bias, 3.5)
        nn.init.constant_(self.head_log_var_c[2].bias, -6.0)
        nn.init.constant_(self.head_log_var_r[2].bias, -6.0)

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Forward pass through trunk and heads.
        
        Args:
            x: Input tensor of shape (batch_size, input_dim).
        
        Returns:
            delta_sei_m: Estimated SEI thickness in meters [m].
            soh_c: Estimated capacity retention fraction [0, 1].
            soh_r: Estimated resistance health fraction [0, 1].
            log_var_c: Log variance for SOH_C.
            log_var_r: Log variance for SOH_R.
        """
        # Normalize physical inputs into normalized numerical space
        x_norm = (x + self.shifts) * self.scales
        features = self.trunk(x_norm)

        # Raw output is in nm (+ baseline 5 nm)
        sei_nm = self.head_sei(features) + 5.0
        delta_sei_m = sei_nm * self.config.delta_sei_scale_nm

        soh_c = self.head_soh_c(features)
        soh_r = self.head_soh_r(features)

        # Clamp log variances to prevent numerical instability
        log_var_c = torch.clamp(self.head_log_var_c(features), min=-14.0, max=0.0)
        log_var_r = torch.clamp(self.head_log_var_r(features), min=-14.0, max=0.0)

        return delta_sei_m, soh_c, soh_r, log_var_c, log_var_r

    def predict_with_uncertainty(
        self,
        x: torch.Tensor,
        num_mc_samples: int = 25,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Predict SOH_C and SOH_R with combined epistemic (MC Dropout) and aleatoric uncertainty.
        
        Returns:
            mean_c: Expected SOH_C.
            std_c: Total standard deviation for SOH_C.
            mean_r: Expected SOH_R.
            std_r: Total standard deviation for SOH_R.
        """
        self.eval()
        # Enable dropout during inference for MC sampling
        for m in self.modules():
            if isinstance(m, nn.Dropout):
                m.train()

        mc_preds_c: List[torch.Tensor] = []
        mc_vars_c: List[torch.Tensor] = []
        mc_preds_r: List[torch.Tensor] = []
        mc_vars_r: List[torch.Tensor] = []

        with torch.no_grad():
            for _ in range(num_mc_samples):
                _, s_c, s_r, lv_c, lv_r = self.forward(x)
                mc_preds_c.append(s_c)
                mc_vars_c.append(torch.exp(lv_c))
                mc_preds_r.append(s_r)
                mc_vars_r.append(torch.exp(lv_r))

        stack_c = torch.stack(mc_preds_c)  # (mc_samples, batch, 1)
        stack_vc = torch.stack(mc_vars_c)

        stack_r = torch.stack(mc_preds_r)
        stack_vr = torch.stack(mc_vars_r)

        mean_c = torch.mean(stack_c, dim=0)
        var_epistemic_c = torch.var(stack_c, dim=0)
        var_aleatoric_c = torch.mean(stack_vc, dim=0)
        std_c = torch.sqrt(var_epistemic_c + var_aleatoric_c + 1e-8)

        mean_r = torch.mean(stack_r, dim=0)
        var_epistemic_r = torch.var(stack_r, dim=0)
        var_aleatoric_r = torch.mean(stack_vr, dim=0)
        std_r = torch.sqrt(var_epistemic_r + var_aleatoric_r + 1e-8)

        self.eval()
        return mean_c, std_c, mean_r, std_r
