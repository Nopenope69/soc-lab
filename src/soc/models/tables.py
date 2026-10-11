"""Look-up table interpolation with strict edge clamping (no extrapolation)."""

from typing import Dict, List, Tuple, Union
import numpy as np


class InterpolatedTable1D:
    """1D piecewise linear table interpolation with boundary clamping."""

    def __init__(self, grid_x: List[float], values_y: List[float]):
        if len(grid_x) != len(values_y):
            raise ValueError("grid_x and values_y must have identical lengths")
        if len(grid_x) < 2:
            raise ValueError("grid_x must contain at least 2 points")

        self.grid_x = np.asarray(grid_x, dtype=float)
        self.values_y = np.asarray(values_y, dtype=float)

    def lookup(self, x: float) -> float:
        """Lookup y(x) with strict clamping at boundary endpoints."""
        if x <= self.grid_x[0]:
            return float(self.values_y[0])
        if x >= self.grid_x[-1]:
            return float(self.values_y[-1])
        return float(np.interp(x, self.grid_x, self.values_y))

    def derivative(self, x: float) -> float:
        """Compute dy/dx at x with boundary clamping."""
        if x <= self.grid_x[0]:
            dx = self.grid_x[1] - self.grid_x[0]
            dy = self.values_y[1] - self.values_y[0]
            return float(dy / dx)
        if x >= self.grid_x[-1]:
            idx_last = len(self.grid_x) - 1
            idx_prev = len(self.grid_x) - 2
            dx = self.grid_x[idx_last] - self.grid_x[idx_prev]
            dy = self.values_y[idx_last] - self.values_y[idx_prev]
            return float(dy / dx)

        idx = int(np.searchsorted(self.grid_x, x))
        idx_low = idx - 1
        dx = self.grid_x[idx] - self.grid_x[idx_low]
        dy = self.values_y[idx] - self.values_y[idx_low]
        return float(dy / dx)


class InterpolatedTable2D:
    """2D table interpolation over (Temperature, SOC) with boundary clamping."""

    def __init__(
        self,
        temperatures_c: List[float],
        soc_grid: List[float],
        table_dict: Dict[str, Union[List[float], float]],
    ):
        self.temp_grid = np.asarray(temperatures_c, dtype=float)
        self.soc_grid = np.asarray(soc_grid, dtype=float)
        self.table_dict = table_dict

        # Parse table values per temperature
        self._parsed_tables: Dict[float, np.ndarray] = {}
        for t_val in self.temp_grid:
            # Check key matching as float or string
            t_key_str = str(t_val)
            val_found = None
            if t_key_str in table_dict:
                val_found = table_dict[t_key_str]
            else:
                for k, v in table_dict.items():
                    if float(k) == t_val:
                        val_found = v
                        break

            if val_found is None:
                raise KeyError(f"Temperature point {t_val} not found in table dictionary")

            if isinstance(val_found, (int, float)):
                self._parsed_tables[t_val] = np.full_like(self.soc_grid, float(val_found))
            else:
                self._parsed_tables[t_val] = np.asarray(val_found, dtype=float)

    def _get_bounding_temps(self, temp_c: float) -> Tuple[float, float, float]:
        """Return (t_low, t_high, alpha) with boundary clamping."""
        if temp_c <= self.temp_grid[0]:
            return float(self.temp_grid[0]), float(self.temp_grid[0]), float(0)
        if temp_c >= self.temp_grid[-1]:
            return float(self.temp_grid[-1]), float(self.temp_grid[-1]), float(0)

        idx = int(np.searchsorted(self.temp_grid, temp_c))
        t_low = float(self.temp_grid[idx - 1])
        t_high = float(self.temp_grid[idx])
        dt = t_high - t_low
        alpha = (temp_c - t_low) / dt if dt > 0 else float(0)
        return t_low, t_high, float(alpha)

    def lookup(self, soc: float, temp_c: float) -> float:
        """Lookup table value at (soc, temp_c) with boundary clamping on both axes."""
        # Clamp SOC
        soc_clamped = min(max(soc, float(self.soc_grid[0])), float(self.soc_grid[-1]))

        t_low, t_high, alpha = self._get_bounding_temps(temp_c)

        v_low = float(np.interp(soc_clamped, self.soc_grid, self._parsed_tables[t_low]))
        if t_low == t_high:
            return v_low

        v_high = float(np.interp(soc_clamped, self.soc_grid, self._parsed_tables[t_high]))
        return (1 - alpha) * v_low + alpha * v_high

    def derivative_soc(self, soc: float, temp_c: float) -> float:
        """Compute partial derivative w.r.t SOC: d(value)/d(soc) at (soc, temp_c)."""
        soc_clamped = min(max(soc, float(self.soc_grid[0])), float(self.soc_grid[-1]))

        t_low, t_high, alpha = self._get_bounding_temps(temp_c)

        def _calc_deriv(t_val: float) -> float:
            y_arr = self._parsed_tables[t_val]
            if soc_clamped <= self.soc_grid[0]:
                dx = self.soc_grid[1] - self.soc_grid[0]
                dy = y_arr[1] - y_arr[0]
                return float(dy / dx)
            if soc_clamped >= self.soc_grid[-1]:
                idx_last = len(self.soc_grid) - 1
                idx_prev = len(self.soc_grid) - 2
                dx = self.soc_grid[idx_last] - self.soc_grid[idx_prev]
                dy = y_arr[idx_last] - y_arr[idx_prev]
                return float(dy / dx)

            idx = int(np.searchsorted(self.soc_grid, soc_clamped))
            idx_low = idx - 1
            dx = self.soc_grid[idx] - self.soc_grid[idx_low]
            dy = y_arr[idx] - y_arr[idx_low]
            return float(dy / dx)

        d_low = _calc_deriv(t_low)
        if t_low == t_high:
            return d_low

        d_high = _calc_deriv(t_high)
        return (1 - alpha) * d_low + alpha * d_high

    def invert_soc(self, value: float, temp_c: float) -> float:
        """Invert table to find SOC given value at temperature (requires monotonicity)."""
        t_low, t_high, alpha = self._get_bounding_temps(temp_c)

        y_low = self._parsed_tables[t_low]
        if t_low == t_high:
            y_target = y_low
        else:
            y_high = self._parsed_tables[t_high]
            y_target = (1 - alpha) * y_low + alpha * y_high

        # Strict clamping at endpoints
        if value <= y_target[0]:
            return float(self.soc_grid[0])
        if value >= y_target[-1]:
            return float(self.soc_grid[-1])

        return float(np.interp(value, y_target, self.soc_grid))
