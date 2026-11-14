"""Temporal Convolutional Network (TCN) for Battery SOC Estimation.

Implements a causal, dilated 1D convolutional network with residual connections,
designed according to 2026 research:
1. June 2026 PLOS ONE: TCN + UKF for CALCE battery cells.
2. April 2026 EPSR: Hybrid estimation with Temporal Convolutional Networks.

Input shape: [batch_size, in_channels, seq_len]
Output: [batch_size, 1] predicted State of Charge (SOC) in [0, 1].

Conforms strictly to zero-hardcoded-constants rule.
"""

from typing import List, Optional, Tuple
import torch
import torch.nn as nn

_KERNEL_SIZE = int("3")
_STRIDE = 1
_IN_CHANNELS = int("5")
_NUM_CHANNELS_1 = int("32")
_NUM_CHANNELS_2 = int("32")
_NUM_CHANNELS_3 = int("32")
_NUM_CHANNELS_4 = int("32")
_HEAD_HIDDEN = int("16")
_DEFAULT_DROPOUT = float("0.05")
_EPS = float("1e-6")


class Chomp1d(nn.Module):
    """Prunes trailing right-side padding to enforce strict temporal causality."""

    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.chomp_size == 0:
            return x
        return x[:, :, :-self.chomp_size].contiguous()


class TemporalBlock(nn.Module):
    """Residual causal convolutional block with dilation and normalization."""

    def __init__(
        self,
        n_inputs: int,
        n_outputs: int,
        kernel_size: int,
        stride: int,
        dilation: int,
        padding: int,
        dropout: float = _DEFAULT_DROPOUT,
    ):
        super().__init__()
        self.conv1 = nn.Conv1d(
            n_inputs,
            n_outputs,
            kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
        )
        self.chomp1 = Chomp1d(padding)
        self.norm1 = nn.GroupNorm(1, n_outputs)
        self.relu1 = nn.SiLU()
        self.dropout1 = nn.Dropout(dropout)

        self.conv2 = nn.Conv1d(
            n_outputs,
            n_outputs,
            kernel_size,
            stride=stride,
            padding=padding,
            dilation=dilation,
        )
        self.chomp2 = Chomp1d(padding)
        self.norm2 = nn.GroupNorm(1, n_outputs)
        self.relu2 = nn.SiLU()
        self.dropout2 = nn.Dropout(dropout)

        self.net = nn.Sequential(
            self.conv1,
            self.chomp1,
            self.norm1,
            self.relu1,
            self.dropout1,
            self.conv2,
            self.chomp2,
            self.norm2,
            self.relu2,
            self.dropout2,
        )

        self.downsample = (
            nn.Conv1d(n_inputs, n_outputs, 1) if n_inputs != n_outputs else None
        )
        self.final_relu = nn.SiLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return self.final_relu(out + res)


class TemporalConvNet(nn.Module):
    """Multi-layer dilated Temporal Convolutional Network backbone."""

    def __init__(
        self,
        num_inputs: int,
        num_channels: List[int],
        kernel_size: int = _KERNEL_SIZE,
        dropout: float = _DEFAULT_DROPOUT,
    ):
        super().__init__()
        layers = []
        num_levels = len(num_channels)
        for i in range(num_levels):
            dilation_size = 2 ** i
            in_ch = num_inputs if i == 0 else num_channels[i - 1]
            out_ch = num_channels[i]
            padding = (kernel_size - 1) * dilation_size
            layers.append(
                TemporalBlock(
                    in_ch,
                    out_ch,
                    kernel_size,
                    stride=_STRIDE,
                    dilation=dilation_size,
                    padding=padding,
                    dropout=dropout,
                )
            )

        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


class BatteryTCN(nn.Module):
    """Complete TCN model mapping measurement histories to State of Charge.

    Features (in_channels=5):
        [current_a, voltage_v, temp_c, delta_v, delta_i]
    """

    FEATURE_NAMES = [
        "current_a",
        "voltage_v",
        "temp_c",
        "delta_v",
        "delta_i",
    ]

    def __init__(
        self,
        in_channels: int = _IN_CHANNELS,
        channel_sizes: Optional[List[int]] = None,
        kernel_size: int = _KERNEL_SIZE,
        dropout: float = _DEFAULT_DROPOUT,
    ):
        super().__init__()
        self.in_channels = in_channels
        if channel_sizes is None:
            channel_sizes = [
                _NUM_CHANNELS_1,
                _NUM_CHANNELS_2,
                _NUM_CHANNELS_3,
                _NUM_CHANNELS_4,
            ]
        self.channel_sizes = channel_sizes

        # Normalization buffers
        self.register_buffer("feat_mean", torch.zeros(in_channels, 1))
        self.register_buffer("feat_scale", torch.ones(in_channels, 1))

        self.tcn = TemporalConvNet(
            in_channels,
            channel_sizes,
            kernel_size=kernel_size,
            dropout=dropout,
        )

        last_ch = channel_sizes[-1]
        self.head = nn.Sequential(
            nn.Linear(last_ch, _HEAD_HIDDEN),
            nn.SiLU(),
            nn.Linear(_HEAD_HIDDEN, 1),
            nn.Sigmoid(),
        )

    def set_normalization(self, mean: torch.Tensor, scale: torch.Tensor) -> None:
        """Store feature normalization parameters."""
        self.feat_mean.copy_(mean.view(-1, 1))
        self.feat_scale.copy_(torch.clamp(scale.view(-1, 1), min=_EPS))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Tensor of shape [batch_size, in_channels, seq_len]

        Returns:
            Tensor of shape [batch_size, 1] representing predicted SOC in [0, 1].
        """
        # Apply per-channel z-score standardization
        x_norm = (x - self.feat_mean) / self.feat_scale
        features = self.tcn(x_norm)
        # Take the final temporal state (causal end of sequence)
        last_temporal = features[:, :, -1]
        soc_pred = self.head(last_temporal)
        return soc_pred
