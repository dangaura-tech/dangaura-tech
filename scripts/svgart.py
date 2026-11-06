"""Small helpers for animated SVG artwork (stdlib only).

The main primitive is :func:`orbit_cloud`, which renders a 3D point cloud spinning about
its vertical axis using nothing but SMIL. Under an orthographic camera tilted by ``tilt``
radians, a point at radius ``rho`` from the axis traces an ellipse with semi-axes
``(rho, rho * sin(tilt))``. Every ellipse therefore has the same aspect ratio, so a single
``keyPoints`` table converts uniform angular speed into path-length fractions for all of
them. Depth is suggested by modulating opacity and size with the same phase.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

PALETTE = {
    "bg0": "#0a0d1c",
    "bg1": "#120d2b",
    "bg2": "#071a26",
    "panel": "#0f1326",
    "border": "#262b4d",
    "text": "#e6e8ff",
    "soft": "#aab0d6",
    "muted": "#7a81ab",
    "violet": "#8b7cff",
    "cyan": "#22d3ee",
    "pink": "#f472b6",
    "amber": "#fbbf24",
}

SANS = "'Segoe UI', 'Helvetica Neue', Ubuntu, Arial, sans-serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"


def lerp_color(a: str, b: str, t: float) -> str:
    ca = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def gradient3(t: float, stops=("#22d3ee", "#8b7cff", "#f472b6")) -> str:
    t = min(max(t, 0.0), 1.0)
    return lerp_color(stops[0], stops[1], t * 2) if t < 0.5 else lerp_color(stops[1], stops[2], t * 2 - 1)


def fibonacci_sphere(n: int) -> list[tuple[float, float, float]]:
    golden = math.pi * (3 - math.sqrt(5))
    pts = []
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - y * y)
        pts.append((r * math.cos(golden * i), y, r * math.sin(golden * i)))
    return pts


def _arc_fractions(aspect: float, steps: int) -> list[float]:
    """Path-length fraction travelled after each of ``steps`` equal angle increments."""
    fine = 2000
    acc, cum = 0.0, [0.0]
    for i in range(1, fine + 1):
        a0, a1 = 2 * math.pi * (i - 1) / fine, 2 * math.pi * i / fine
        dx = math.sin(a1) - math.sin(a0)
        dy = aspect * (math.cos(a1) - math.cos(a0))
        acc += math.hypot(dx, dy)
        cum.append(acc)
    return [cum[round(k * fine / steps)] / acc for k in range(steps + 1)]


@dataclass
class Orbit:
    cx: float
    cy: float
    scale: float
    tilt: float = math.radians(20)
    period: float = 18.0
    steps: int = 24

    def __post_init__(self) -> None:
        s = self.steps
        self.key_points = ";".join(f"{f:.4f}" for f in _arc_fractions(math.sin(self.tilt), s))
        self.key_times = ";".join(f"{k / s:.4f}" for k in range(s + 1))
        depth = [math.cos(2 * math.pi * k / s) for k in range(s + 1)]
        self.opacity = ";".join(f"{0.22 + 0.78 * (d + 1) / 2:.2f}" for d in depth)
        self.depth = depth

    def project(self, x: float, y: float, z: float, phi: float = 0.0) -> tuple[float, float]:
        rho, phi0 = math.hypot(x, z), math.atan2(x, z) + phi
        sx = self.cx + self.scale * rho * math.sin(phi0)
        sy = self.cy - self.scale * y * math.cos(self.tilt) + self.scale * rho * math.cos(phi0) * math.sin(self.tilt)
        return sx, sy

    def point(self, x: float, y: float, z: float, r: float, fill: str | None = None) -> str:
        """One point of the cloud; ``fill=None`` inherits the parent group's fill."""
        rho = math.hypot(x, z) * self.scale
        yc = self.cy - self.scale * y * math.cos(self.tilt)
        f = f' fill="{fill}"' if fill else ""
        if rho < 0.8:
            return f'<circle cx="{self.cx:.1f}" cy="{yc:.1f}" r="{r:.2f}"{f} opacity=".6"/>'
        b = rho * math.sin(self.tilt)
        phase = (math.atan2(x, z) % (2 * math.pi)) / (2 * math.pi)
        begin = f"-{phase * self.period:.2f}s"
        path = (
            f"M{self.cx:.1f},{yc + b:.1f}A{rho:.1f},{b:.1f} 0 0 0 {self.cx:.1f},{yc - b:.1f}"
            f"A{rho:.1f},{b:.1f} 0 0 0 {self.cx:.1f},{yc + b:.1f}"
        )
        return (
            f'<circle r="{r:.2f}"{f}>'
            f'<animateMotion dur="{self.period}s" begin="{begin}" repeatCount="indefinite" path="{path}" '
            f'keyPoints="{self.key_points}" keyTimes="{self.key_times}" calcMode="linear"/>'
            f'<animate attributeName="opacity" dur="{self.period}s" begin="{begin}" repeatCount="indefinite" '
            f'values="{self.opacity}"/></circle>'
        )

    def track(self, x: float, y: float, z: float) -> tuple[str, str]:
        """``values`` strings for the screen x/y of a point over one period (for lines, icons)."""
        xs, ys = [], []
        for k in range(self.steps + 1):
            sx, sy = self.project(x, y, z, 2 * math.pi * k / self.steps)
            xs.append(f"{sx:.1f}")
            ys.append(f"{sy:.1f}")
        return ";".join(xs), ";".join(ys)


def orbit_cloud(orbit: Orbit, points, radius: float = 2.2, color=None) -> str:
    """Render ``points`` (x, y, z in [-1, 1]) colour-coded by height unless ``color`` is given."""
    out = []
    for x, y, z in points:
        fill = color or gradient3((1 - y) / 2)
        out.append(orbit.point(x, y, z, radius, fill))
    return "".join(out)


def pill(x: float, y: float, label: str, color: str, size: int = 13, char_w: float = 0.6) -> tuple[str, float]:
    """A rounded tag. Width is estimated from a monospace advance so layout is predictable."""
    w = len(label) * size * char_w + 22
    h = size + 13
    svg = (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2}" fill="{color}" fill-opacity=".12" '
        f'stroke="{color}" stroke-opacity=".45"/>'
        f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + size * 0.36:.1f}" text-anchor="middle" '
        f'font-family="{MONO}" font-size="{size}" fill="{color}">{label}</text>'
    )
    return svg, w
