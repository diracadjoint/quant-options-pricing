"""Projected SOR for tridiagonal option obstacle problems."""

from dataclasses import dataclass
from math import isfinite


class ConvergenceError(RuntimeError):
    """A numerical solver failed its configured stopping criterion."""


@dataclass(frozen=True)
class PSORResult:
    values: tuple[float, ...]
    iterations: int
    residual: float
    update: float
    obstacle_violation: float
    dual_violation: float


def solve_psor(
    lower: list[float], diagonal: list[float], upper: list[float],
    rhs: list[float], obstacle: list[float], initial: list[float], *,
    scale: float, tolerance: float = 1e-8, omega: float = 1.2,
    max_iterations: int = 10000,
) -> PSORResult:
    """Solve v>=g, Av-b>=0, (v-g)*(Av-b)=0 for a strict M-matrix.

    Stop only when both update and ||min(v-g, Av-b)||inf divided by scale
    meet tolerance. Violations are also scaled. Raise ConvergenceError on
    iteration exhaustion. Off-diagonals have length n-1; other vectors n.
    """
    n = len(diagonal)
    if n == 0 or any(len(x) != n for x in (rhs, obstacle, initial)) or len(lower) != n-1 or len(upper) != n-1:
        raise ValueError("incompatible tridiagonal vector lengths")
    if not all(isfinite(x) for vector in (lower, diagonal, upper, rhs, obstacle, initial) for x in vector):
        raise ValueError("PSOR vectors must be finite")
    if not isfinite(scale) or scale <= 0 or not isfinite(tolerance) or tolerance <= 0:
        raise ValueError("scale and tolerance must be finite and positive")
    if not isfinite(omega) or not 0 < omega < 2:
        raise ValueError("omega must be in (0, 2)")
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    for i, diagonal_i in enumerate(diagonal):
        left = lower[i-1] if i else 0.0
        right = upper[i] if i < n-1 else 0.0
        if left > 0 or right > 0 or diagonal_i <= abs(left)+abs(right):
            raise ValueError("PSOR requires a strictly diagonally dominant M-matrix")
    v = [max(x, g) for x, g in zip(initial, obstacle)]
    for iteration in range(1, max_iterations+1):
        update = 0.0
        for i in range(n):
            left = lower[i-1] * v[i-1] if i else 0.0
            right = upper[i] * v[i+1] if i < n-1 else 0.0
            relaxed = (1-omega)*v[i] + omega*(rhs[i]-left-right)/diagonal[i]
            if not isfinite(relaxed):
                raise ConvergenceError("PSOR produced nonfinite values")
            candidate = max(obstacle[i], relaxed)
            update = max(update, abs(candidate-v[i])/scale)
            v[i] = candidate
        residual = obstacle_violation = dual_violation = 0.0
        for i in range(n):
            w = diagonal[i]*v[i]-rhs[i]
            if i:
                w += lower[i-1]*v[i-1]
            if i < n-1:
                w += upper[i]*v[i+1]
            if not isfinite(w):
                raise ConvergenceError("PSOR produced nonfinite residual")
            slack = v[i]-obstacle[i]
            residual = max(residual, abs(min(slack, w))/scale)
            obstacle_violation = max(obstacle_violation, -slack/scale)
            dual_violation = max(dual_violation, -w/scale)
        if not all(isfinite(x) for x in (*v, residual, update)):
            raise ConvergenceError("PSOR produced nonfinite values")
        if residual <= tolerance and update <= tolerance:
            return PSORResult(tuple(v), iteration, residual, update, obstacle_violation, dual_violation)
    raise ConvergenceError(f"PSOR failed after {max_iterations} iterations; residual={residual:.3g}, update={update:.3g}")
