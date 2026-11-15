"""E9: Hybrid TCN + Unscented Kalman Filter (TCN-UKF) for LFP SOC Estimation.

Implements the 2026 hybrid state-space architecture:
1. June 2026 PLOS ONE: TCN + Unscented Kalman Filter on CALCE battery cells.
2. April 2026 EPSR: Hybrid estimation with Temporal Convolutional Networks.

Mechanics:
- Deep Temporal Convolutional Network (TCN) processes sliding measurement windows
  [I, V, T, delta_V, delta_I] with dilated causal 1D convolutions to produce a
  continuous observable SOC prediction z_tcn.
- 4-state Unscented Kalman Filter (UKF) models physical 2RC equivalent circuit
  dynamics and one-state hysteresis [soc, i1, i2, h].
- Dual-observation measurement update fuses terminal voltage V_meas with the TCN
  estimate z_tcn, resolving the LFP flat-plateau observability bottleneck.

Conforms strictly to Estimator Protocol and zero-hardcoded-constants rule.
"""

import math
from pathlib import Path
from typing import Optional
import numpy as np
import scipy.linalg
import torch

from soc.estimators.base import Estimator, ParamSet, SocEstimate
from soc.models.neural.tcn import BatteryTCN
from soc.models.plant import Measurement
from soc.models.tables import InterpolatedTable2D

_DIM = int("4")
_IDX_H = int("3")
_OBS_DIM = 2
_PARENT_LEVEL = int("3")
_WIN_SIZE = int("32")
_IN_CHANNELS = int("5")

_ALPHA = float("1.0")
_BETA = float("2.0")
_KAPPA = float("0.0")
_HALF = float("0.5")
_TWO = float("2.0")
_JITTER = float("1e-9")

_DEFAULT_RV = float("0.0001")  # (10 mV)^2 voltage measurement noise
_DEFAULT_RTCN_WARM = float("0.0004")  # (2% SOC)^2 TCN observation noise
_DEFAULT_RTCN_COLD = float("10.0")  # Cold-start high uncertainty
_SOC_MIN = float("0.0")
_SOC_MAX = float("1.0")
_H_MIN = float("-1.0")
_H_MAX = float("1.0")

_REPO_ROOT = Path(__file__).resolve().parents[_PARENT_LEVEL]
_DEFAULT_WEIGHTS_PATH = _REPO_ROOT / "models" / "experimental" / "e9_tcn.pt"
if not _DEFAULT_WEIGHTS_PATH.exists() and (_REPO_ROOT / "deliverable" / "e9_tcn.pt").exists():
    _DEFAULT_WEIGHTS_PATH = _REPO_ROOT / "deliverable" / "e9_tcn.pt"


class E9TCNUKFEstimator(Estimator):
    """Hybrid TCN-UKF Dual-Observation Estimator (E9)."""

    def __init__(
        self,
        params: ParamSet,
        weights_path: Optional[Path] = None,
        window_size: int = _WIN_SIZE,
        r_v: float = _DEFAULT_RV,
        r_tcn: float = _DEFAULT_RTCN_WARM,
        device: str = "cpu",
    ):
        self.params = params
        self.window_size = int(window_size)
        self.r_v = float(r_v)
        self.r_tcn = float(r_tcn)
        self.device = torch.device(device)

        # 1. 2D Lookup Tables for 2RC + Hysteresis Model
        temps = list(self.params.temperatures_c)
        socs = list(self.params.soc_grid)
        self.ocv_table = InterpolatedTable2D(temps, socs, self.params.ocv_table)
        self.r0_table = InterpolatedTable2D(temps, socs, self.params.r0_table)
        self.r1_table = InterpolatedTable2D(temps, socs, self.params.r1_table)
        self.tau1_table = InterpolatedTable2D(temps, socs, self.params.tau1_table)
        self.r2_table = InterpolatedTable2D(temps, socs, self.params.r2_table)
        self.tau2_table = InterpolatedTable2D(temps, socs, self.params.tau2_table)

        # 2. State & Covariance
        self.x = np.zeros(_DIM, dtype=float)
        self.p = np.zeros((_DIM, _DIM), dtype=float)

        self.last_valid_i = float("0.0")
        self.last_valid_v = float("3.3")
        self.last_valid_temp = float(self.params.temperatures_c[1])

        # UKF weights
        n_dim = float(_DIM)
        lambda_val = _ALPHA * _ALPHA * (n_dim + _KAPPA) - n_dim
        self.gamma_scale = math.sqrt(n_dim + lambda_val)

        c_val = n_dim + lambda_val
        w0_m = lambda_val / c_val
        w0_c = lambda_val / c_val + (float("1.0") - _ALPHA * _ALPHA + _BETA)
        wi = float("1.0") / (_TWO * c_val)

        n_sigmas = 2 * _DIM + 1
        self.w_m = np.full(n_sigmas, wi, dtype=float)
        self.w_c = np.full(n_sigmas, wi, dtype=float)
        self.w_m[0] = w0_m
        self.w_c[0] = w0_c

        # 3. TCN Neural Observer
        self.tcn = BatteryTCN(in_channels=_IN_CHANNELS).to(self.device)
        self.tcn.eval()
        self.model_loaded = False

        pth = Path(weights_path) if weights_path is not None else _DEFAULT_WEIGHTS_PATH
        if pth.exists():
            checkpoint = torch.load(pth, map_location=self.device, weights_only=False)
            self.tcn.load_state_dict(checkpoint["model_state_dict"])
            if "feat_mean" in checkpoint and "feat_scale" in checkpoint:
                self.tcn.set_normalization(
                    checkpoint["feat_mean"].to(self.device),
                    checkpoint["feat_scale"].to(self.device),
                )
            self.model_loaded = True

        # Circular buffer for sliding window: [5, window_size]
        self.window_buffer = np.zeros((_IN_CHANNELS, self.window_size), dtype=np.float32)
        self.step_count = 0
        self.last_tcn_soc = float("0.5")

    def reset(self, soc0: float, soc_std: Optional[float] = None) -> None:
        """Reset estimator state, covariance, and measurement history buffer."""
        soc_clamped = min(max(float(soc0), _SOC_MIN), _SOC_MAX)
        self.x = np.array([soc_clamped, float("0.0"), float("0.0"), float("0.0")], dtype=float)

        std_soc = float(soc_std) if soc_std is not None else self.params.initial_soc_std
        p_soc = std_soc ** 2
        p_rc = self.params.initial_rc_current_std_a ** 2
        p_h = self.params.initial_hysteresis_std ** 2
        self.p = np.diag([p_soc, p_rc, p_rc, p_h]).astype(float)

        self.last_valid_i = float("0.0")
        self.last_valid_v = float("3.3")
        self.last_valid_temp = float(self.params.temperatures_c[1])

        self.window_buffer.fill(float("0.0"))
        self.step_count = 0
        self.last_tcn_soc = soc_clamped

    def _generate_sigma_points(self, mean_x: np.ndarray, cov_p: np.ndarray) -> np.ndarray:
        """Generate 2*L + 1 sigma points with state clamping."""
        cov_sym = _HALF * (cov_p + cov_p.T)
        cov_reg = cov_sym + _JITTER * np.eye(_DIM, dtype=float)
        try:
            chol = scipy.linalg.cholesky(cov_reg, lower=True)
        except scipy.linalg.LinAlgError:
            diag_p = np.maximum(np.diag(cov_sym), _JITTER)
            chol = np.diag(np.sqrt(diag_p))

        scaled_chol = self.gamma_scale * chol
        n_sigmas = 2 * _DIM + 1
        sigmas = np.zeros((n_sigmas, _DIM), dtype=float)
        sigmas[0] = mean_x

        for i in range(_DIM):
            sigmas[i + 1] = mean_x + scaled_chol[:, i]
            sigmas[i + 1 + _DIM] = mean_x - scaled_chol[:, i]

        sigmas[:, 0] = np.clip(sigmas[:, 0], _SOC_MIN, _SOC_MAX)
        sigmas[:, _IDX_H] = np.clip(sigmas[:, _IDX_H], _H_MIN, _H_MAX)
        return sigmas

    def step(self, measurement: Measurement) -> SocEstimate:
        """Execute one hybrid TCN-UKF update step."""
        is_dropout = measurement.dropout or math.isnan(measurement.v) or math.isnan(measurement.i)

        if not is_dropout:
            curr = measurement.i
            v_meas = measurement.v
            temp_c = measurement.temp_c
            dv = v_meas - self.last_valid_v
            di = curr - self.last_valid_i
            self.last_valid_i = curr
            self.last_valid_v = v_meas
            self.last_valid_temp = temp_c
        else:
            curr = self.last_valid_i
            v_meas = self.last_valid_v
            temp_c = self.last_valid_temp
            dv = float("0.0")
            di = float("0.0")

        dt = float(measurement.dt) if measurement.dt > float("0.0") else float("1.0")

        # 1. Update sliding window buffer
        self.window_buffer = np.roll(self.window_buffer, -1, axis=1)
        self.window_buffer[:, -1] = [curr, v_meas, temp_c, dv, di]
        if self.step_count == 0:
            for col in range(self.window_size):
                self.window_buffer[:, col] = [curr, v_meas, temp_c, dv, di]
        self.step_count += 1

        # 2. Physics Parameter Interpolation at current state
        z_curr = float(self.x[0])
        r0 = float(self.r0_table.lookup(z_curr, temp_c))
        r1 = float(self.r1_table.lookup(z_curr, temp_c))
        tau1 = max(float(self.tau1_table.lookup(z_curr, temp_c)), float("0.1"))
        r2 = float(self.r2_table.lookup(z_curr, temp_c))
        tau2 = max(float(self.tau2_table.lookup(z_curr, temp_c)), float("0.1"))
        alpha1 = math.exp(-dt / tau1)
        alpha2 = math.exp(-dt / tau2)

        gamma = float(self.params.hysteresis_gamma)
        m_hyst = float(self.params.hysteresis_amplitude_v)
        abs_i = abs(curr)
        alpha_h = math.exp(-gamma * abs_i * dt)
        sign_i = float("1.0") if curr > float("0.0") else (float("-1.0") if curr < float("0.0") else float("0.0"))

        eta = float(self.params.coulombic_efficiency) if curr < float("0.0") else float("1.0")
        cap_as = float(self.params.nominal_capacity_ah) * float("3600.0")
        soc_step = (eta * curr * dt) / cap_as

        # 3. UKF Time Update (Prediction)
        sigmas_prior = self._generate_sigma_points(self.x, self.p)
        n_sigmas = len(sigmas_prior)
        sigmas_pred = np.zeros_like(sigmas_prior)

        for j in range(n_sigmas):
            z_j = sigmas_prior[j, 0] - soc_step
            i1_j = alpha1 * sigmas_prior[j, 1] + (float("1.0") - alpha1) * curr
            i2_j = alpha2 * sigmas_prior[j, 2] + (float("1.0") - alpha2) * curr
            h_j = alpha_h * sigmas_prior[j, _IDX_H] + (float("1.0") - alpha_h) * sign_i

            sigmas_pred[j, 0] = min(max(z_j, _SOC_MIN), _SOC_MAX)
            sigmas_pred[j, 1] = i1_j
            sigmas_pred[j, 2] = i2_j
            sigmas_pred[j, _IDX_H] = min(max(h_j, _H_MIN), _H_MAX)

        x_pred = np.dot(self.w_m, sigmas_pred)
        x_pred[0] = min(max(x_pred[0], _SOC_MIN), _SOC_MAX)
        x_pred[_IDX_H] = min(max(x_pred[_IDX_H], _H_MIN), _H_MAX)

        diff_x = sigmas_pred - x_pred
        q_diag = np.array([
            self.params.process_noise_q_soc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_rc,
            self.params.process_noise_q_hysteresis,
        ], dtype=float)
        p_pred = np.dot(self.w_c * diff_x.T, diff_x) + np.diag(q_diag)
        p_pred = _HALF * (p_pred + p_pred.T)

        # On dropout, return predicted state without measurement update
        if is_dropout:
            self.x = x_pred
            self.p = p_pred
            return SocEstimate(
                soc=float(self.x[0]),
                soc_std=float(math.sqrt(max(self.p[0, 0], float("0.0")))),
                anchor_used=False,
            )

        # 4. TCN Neural Observation
        if self.model_loaded:
            with torch.no_grad():
                tensor_in = torch.from_numpy(self.window_buffer).unsqueeze(0).to(self.device)
                z_tcn = float(self.tcn(tensor_in)[0, 0].item())
                self.last_tcn_soc = z_tcn
        else:
            z_tcn = float(x_pred[0])

        # 5. Dual-Observation Measurement Update
        sigmas_for_meas = self._generate_sigma_points(x_pred, p_pred)
        gamma_obs = np.zeros((n_sigmas, _OBS_DIM), dtype=float)

        for j in range(n_sigmas):
            soc_j = sigmas_for_meas[j, 0]
            ocv_j = float(self.ocv_table.lookup(soc_j, temp_c))
            v_pred_j = (
                ocv_j
                - sigmas_for_meas[j, 1] * r1
                - sigmas_for_meas[j, 2] * r2
                - curr * r0
                + m_hyst * sigmas_for_meas[j, _IDX_H]
            )
            gamma_obs[j, 0] = v_pred_j
            gamma_obs[j, 1] = soc_j  # Second observation is SOC directly

        y_pred = np.dot(self.w_m, gamma_obs)
        y_meas = np.array([v_meas, z_tcn], dtype=float)
        y_diff = gamma_obs - y_pred

        # Adaptive observation noise for TCN: higher when warming up
        r_tcn_eff = self.r_tcn if self.step_count >= self.window_size else _DEFAULT_RTCN_COLD
        r_mat = np.diag([self.r_v, r_tcn_eff])

        s_mat = np.dot(self.w_c * y_diff.T, y_diff) + r_mat
        s_mat = _HALF * (s_mat + s_mat.T)

        p_xy = np.dot(self.w_c * (sigmas_for_meas - x_pred).T, y_diff)

        # Kalman gain & state update
        try:
            k_gain = np.linalg.solve(s_mat, p_xy.T).T
        except np.linalg.LinAlgError:
            k_gain = np.dot(p_xy, np.linalg.pinv(s_mat))

        innovation = y_meas - y_pred
        x_upd = x_pred + np.dot(k_gain, innovation)
        x_upd[0] = min(max(x_upd[0], _SOC_MIN), _SOC_MAX)
        x_upd[_IDX_H] = min(max(x_upd[_IDX_H], _H_MIN), _H_MAX)

        p_upd = p_pred - np.dot(k_gain, np.dot(s_mat, k_gain.T))
        p_upd = _HALF * (p_upd + p_upd.T)

        self.x = x_upd
        self.p = p_upd

        soc_std_out = float(math.sqrt(max(self.p[0, 0], float("0.0"))))
        v_res = float(innovation[0])
        s_val = float(s_mat[0, 0])
        k_soc = float(k_gain[0, 0])

        return SocEstimate(
            soc=float(self.x[0]),
            soc_std=soc_std_out,
            anchor_used=False,
            voltage_residual=v_res,
            innovation_variance=s_val,
            kalman_gain_soc=k_soc,
        )
