"""Physics-informed loss functions for battery degradation PINN.

Implements:
1. Anchored Heteroscedastic negative log-likelihood data loss for SOH_C and SOH_R
2. Autograd-based SEI diffusion and reaction ODE residual losses
3. Throughput-monotonicity penalty loss
4. Loss-of-Lithium-Inventory (LLI) physical coupling loss
5. Modular toggles for controlled ablation experiments
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from soh.models.pinn.sei_kinetics import R_GAS, SeiGrowthMechanism, SeiKineticsParameters


@dataclass
class LossWeights:
    """Hyperparameter weights for multi-objective PINN training."""

    lambda_data_c: float = 1.0
    lambda_data_r: float = 1.0
    lambda_physics: float = 0.01
    lambda_monotonicity: float = 0.01
    lambda_lli: float = 0.05


class PinnLossFunction(nn.Module):
    """Multi-objective loss function combining empirical data fit with physical governing equations."""

    def __init__(
        self,
        kinetics_params: Optional[SeiKineticsParameters] = None,
        weights: Optional[LossWeights] = None,
    ):
        super().__init__()
        self.params = kinetics_params or SeiKineticsParameters()
        self.weights = weights or LossWeights()

    def heteroscedastic_nll(
        self,
        y_true: torch.Tensor,
        y_pred: torch.Tensor,
        log_var: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Anchored Heteroscedastic Loss combining direct MSE with Gaussian NLL."""
        diff_sq = (y_true - y_pred) ** 2
        clamped_lv = torch.clamp(log_var, min=-12.0, max=0.0)
        precision = torch.exp(-clamped_lv)
        
        # Primary MSE signal + calibrated variance penalty
        loss_pointwise = diff_sq + 0.02 * (0.5 * precision * diff_sq + 0.5 * clamped_lv)

        if mask is not None:
            masked_loss = loss_pointwise * mask
            denom = torch.clamp(mask.sum(), min=1.0)
            return masked_loss.sum() / denom
        return torch.mean(loss_pointwise)

    def compute_physics_residual(
        self,
        x_inputs: torch.Tensor,
        delta_sei_m: torch.Tensor,
        mechanism: Optional[SeiGrowthMechanism] = None,
    ) -> torch.Tensor:
        """Compute the governing SEI ODE residual via PyTorch autograd:
        
        Diffusion: residual = d(delta)/dt - [ (k_diff / (2 * delta)) * Arrhenius(T) * g(I, SOC) ]
        Reaction:  residual = d(delta)/dt - [ k_rxn * Arrhenius(T) * g(I, SOC) ]
        """
        mech = mechanism or self.params.mechanism

        # Compute gradient of delta_sei with respect to x_inputs
        grads = torch.autograd.grad(
            outputs=delta_sei_m,
            inputs=x_inputs,
            grad_outputs=torch.ones_like(delta_sei_m),
            create_graph=True,
            retain_graph=True,
            only_inputs=True,
        )[0]

        # Column 0 is time in seconds (t_s)
        d_delta_dt = grads[:, 0:1]

        # Extract operating condition inputs
        temp_k = torch.clamp(x_inputs[:, 2:3], min=200.0, max=350.0)
        current_a = x_inputs[:, 3:4]
        soc = torch.clamp(x_inputs[:, 4:5], min=0.0, max=1.0)

        # Arrhenius factor
        ea = self.params.activation_energy_j
        t_ref = self.params.t_ref_k
        arrh_exp = -(ea / R_GAS) * (1.0 / temp_k - 1.0 / t_ref)
        arrhenius = torch.exp(torch.clamp(arrh_exp, min=-20.0, max=20.0))

        # Operating factor g(I, SOC)
        c_rate = torch.abs(current_a) / max(0.1, self.params.nominal_1c_current_a)
        current_acc = self.params.beta_current * (c_rate ** self.params.alpha_current)
        soc_acc = self.params.beta_soc * (soc - 0.5)
        g_factor = torch.clamp(1.0 + current_acc + soc_acc, min=0.1)

        # Theoretical growth rate based on kinetic regime
        if mech == SeiGrowthMechanism.SOLVENT_DIFFUSION_LIMITED:
            safe_delta = torch.clamp(delta_sei_m, min=1.0e-11)
            target_rate = (self.params.k_sei_diffusion / (2.0 * safe_delta)) * arrhenius * g_factor
        else:
            target_rate = self.params.k_sei_reaction * arrhenius * g_factor

        # Normalized residual (scale by expected typical rate ~1e-8 m/s for stable gradient magnitude)
        rate_scale = 1.0e-8
        residual = (d_delta_dt - target_rate) / rate_scale
        return torch.mean(residual ** 2)

    def compute_monotonicity_loss(
        self,
        x_inputs: torch.Tensor,
        soh_c: torch.Tensor,
    ) -> torch.Tensor:
        """Penalize positive capacity gradient with respect to charge throughput (Ah):
        
        Capacity cannot increase irreversibly as cumulative throughput increases.
        """
        grads = torch.autograd.grad(
            outputs=soh_c,
            inputs=x_inputs,
            grad_outputs=torch.ones_like(soh_c),
            create_graph=True,
            retain_graph=True,
            only_inputs=True,
        )[0]

        # Column 1 is cumulative Ah throughput
        d_sohc_dah = grads[:, 1:2]

        # Non-negative penalty for violations (d_sohc_dah > 0)
        violations = F.relu(d_sohc_dah)
        return torch.mean(violations ** 2)

    def compute_lli_loss(
        self,
        delta_sei_m: torch.Tensor,
        soh_c: torch.Tensor,
    ) -> torch.Tensor:
        """Loss of Lithium Inventory (LLI) algebraic coupling:
        
        (1.0 - SOH_C) should be proportional to delta_sei - delta_sei_0.
        """
        delta_growth = torch.clamp(delta_sei_m - self.params.delta_sei_0, min=0.0)
        expected_lli_fade = self.params.chi_lli * delta_growth
        actual_fade = 1.0 - soh_c
        return torch.mean((actual_fade - expected_lli_fade) ** 2)

    def forward(
        self,
        x_inputs: torch.Tensor,
        delta_sei_m: torch.Tensor,
        soh_c_pred: torch.Tensor,
        soh_r_pred: torch.Tensor,
        log_var_c: torch.Tensor,
        log_var_r: torch.Tensor,
        y_c_true: torch.Tensor,
        y_r_true: torch.Tensor,
        mask_c: Optional[torch.Tensor] = None,
        mask_r: Optional[torch.Tensor] = None,
        enable_physics: bool = True,
        enable_monotonicity: bool = True,
        enable_lli: bool = True,
        physics_mechanism: Optional[SeiGrowthMechanism] = None,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """Calculate total loss with component breakdown."""
        loss_data_c = self.heteroscedastic_nll(y_c_true, soh_c_pred, log_var_c, mask_c)
        loss_data_r = self.heteroscedastic_nll(y_r_true, soh_r_pred, log_var_r, mask_r)

        total_loss = self.weights.lambda_data_c * loss_data_c + self.weights.lambda_data_r * loss_data_r
        metrics = {
            "loss_data_c": float(loss_data_c.item()),
            "loss_data_r": float(loss_data_r.item()),
            "loss_physics": 0.0,
            "loss_mono": 0.0,
            "loss_lli": 0.0,
        }

        if enable_physics:
            loss_phys = self.compute_physics_residual(x_inputs, delta_sei_m, mechanism=physics_mechanism)
            total_loss = total_loss + self.weights.lambda_physics * loss_phys
            metrics["loss_physics"] = float(loss_phys.item())

        if enable_monotonicity:
            loss_mono = self.compute_monotonicity_loss(x_inputs, soh_c_pred)
            total_loss = total_loss + self.weights.lambda_monotonicity * loss_mono
            metrics["loss_mono"] = float(loss_mono.item())

        if enable_lli:
            loss_lli = self.compute_lli_loss(delta_sei_m, soh_c_pred)
            total_loss = total_loss + self.weights.lambda_lli * loss_lli
            metrics["loss_lli"] = float(loss_lli.item())

        metrics["loss_total"] = float(total_loss.item())
        return total_loss, metrics
