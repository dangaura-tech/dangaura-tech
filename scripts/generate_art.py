"""Render the static, animated artwork used by the profile README into ``assets/``.

    python scripts/generate_art.py

Everything is plain SVG + SMIL, so it animates inside GitHub's image proxy without
JavaScript, external fonts or third-party services.
"""

from __future__ import annotations

import math
import random
from html import escape
from pathlib import Path

from svgart import MONO, PALETTE as P, SANS, Orbit, fibonacci_sphere, orbit_cloud, pill

ROOT = Path(__file__).resolve().parents[1] / "assets"


def svg(width: int, height: int, body: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{escape(label)}">{body}</svg>\n'
    )


def mono_text(x, y, text, size, fill, **extra) -> str:
    attrs = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in extra.items())
    return (
        f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" fill="{fill}" '
        f'textLength="{len(text) * size * 0.6:.1f}" lengthAdjust="spacingAndGlyphs" {attrs}>{escape(text)}</text>'
    )


def typed_lines(x, y, lines, size, colors, cycle, uid) -> str:
    """Lines revealed one after another, typewriter style, with a following cursor."""
    out, n = [], len(lines)
    cursor_x, cursor_t = [], []
    for i, (line, color) in enumerate(zip(lines, colors)):
        w = len(line) * size * 0.6
        s = i / n
        span = 1 / n
        t = [0, s, s + 0.38 * span, s + 0.88 * span, s + 0.97 * span, 1]
        v = [0, 0, w, w, 0, 0]
        if i == 0:
            t, v = t[1:], v[1:]
        kt = ";".join(f"{a:.4f}" for a in t)
        out.append(
            f'<clipPath id="{uid}{i}"><rect x="{x}" y="{y - size}" height="{size * 1.5}" width="0">'
            f'<animate attributeName="width" dur="{cycle}s" repeatCount="indefinite" keyTimes="{kt}" '
            f'values="{";".join(f"{a:.1f}" for a in v)}"/></rect></clipPath>'
            f'<g clip-path="url(#{uid}{i})">{mono_text(x, y, line, size, color)}</g>'
        )
        cursor_t += t
        cursor_x += [x + a + 3 for a in v]
    # cursor: merge the per-line tracks into one monotonically timed animation
    pairs = sorted(set(zip(cursor_t, cursor_x)))
    dedup = {}
    for a, b in pairs:
        dedup[round(a, 4)] = b
    kt = sorted(dedup)
    if kt[0] != 0:
        kt = [0.0] + kt
        dedup[0.0] = x + 3
    if kt[-1] != 1:
        kt.append(1.0)
        dedup[1.0] = x + 3
    out.append(
        f'<rect y="{y - size * 0.85:.1f}" width="{size * 0.55:.1f}" height="{size * 1.05:.1f}" fill="{P["cyan"]}">'
        f'<animate attributeName="x" dur="{cycle}s" repeatCount="indefinite" '
        f'keyTimes="{";".join(f"{a:.4f}" for a in kt)}" values="{";".join(f"{dedup[a]:.1f}" for a in kt)}"/>'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" repeatCount="indefinite"/>'
        f"</rect>"
    )
    return "".join(out)


def backdrop(w, h, uid, rx=18) -> str:
    return f"""
<defs>
  <linearGradient id="{uid}bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{P["bg0"]}"/><stop offset=".55" stop-color="{P["bg1"]}"/><stop offset="1" stop-color="{P["bg2"]}"/>
  </linearGradient>
  <linearGradient id="{uid}edge" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{P["violet"]}"/><stop offset=".5" stop-color="{P["cyan"]}"/><stop offset="1" stop-color="{P["pink"]}"/>
  </linearGradient>
  <radialGradient id="{uid}g1"><stop offset="0" stop-color="{P["violet"]}" stop-opacity=".55"/><stop offset="1" stop-color="{P["violet"]}" stop-opacity="0"/></radialGradient>
  <radialGradient id="{uid}g2"><stop offset="0" stop-color="{P["cyan"]}" stop-opacity=".35"/><stop offset="1" stop-color="{P["cyan"]}" stop-opacity="0"/></radialGradient>
  <pattern id="{uid}dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="1.1" fill="#ffffff" fill-opacity=".07"/></pattern>
  <clipPath id="{uid}clip"><rect width="{w}" height="{h}" rx="{rx}"/></clipPath>
</defs>
<g clip-path="url(#{uid}clip)">
  <rect width="{w}" height="{h}" fill="url(#{uid}bg)"/>
  <rect width="{w}" height="{h}" fill="url(#{uid}dots)"/>
</g>"""


def frame_edge(w, h, uid, rx=18) -> str:
    return (
        f'<rect x=".75" y=".75" width="{w - 1.5}" height="{h - 1.5}" rx="{rx}" fill="none" '
        f'stroke="url(#{uid}edge)" stroke-opacity=".55" stroke-width="1.5"/>'
    )


def camera_icon(orbit: Orbit, x, y, z, color, size=1.0) -> str:
    xs, ys = orbit.track(x, y, z)
    tr = ";".join(f"{a} {b}" for a, b in zip(xs.split(";"), ys.split(";")))
    rho, phi0 = math.hypot(x, z), math.atan2(x, z)
    op = ";".join(f"{0.35 + 0.65 * (math.cos(phi0 + 2 * math.pi * k / orbit.steps) + 1) / 2:.2f}" for k in range(orbit.steps + 1))
    dur = f'dur="{orbit.period}s" repeatCount="indefinite"'
    s = size
    return (
        f'<line x2="{orbit.cx}" y2="{orbit.cy}" stroke="{color}" stroke-opacity=".35" stroke-dasharray="3 5">'
        f'<animate attributeName="x1" {dur} values="{xs}"/><animate attributeName="y1" {dur} values="{ys}"/></line>'
        f"<g>"
        f'<animateTransform attributeName="transform" type="translate" {dur} values="{tr}"/>'
        f'<animate attributeName="opacity" {dur} values="{op}"/>'
        f'<rect x="{-9 * s}" y="{-6 * s}" width="{14 * s}" height="{12 * s}" rx="{2 * s}" fill="{P["bg0"]}" stroke="{color}" stroke-width="1.6"/>'
        f'<path d="M{5 * s},{-3 * s} L{11 * s},{-6 * s} L{11 * s},{6 * s} L{5 * s},{3 * s}Z" fill="{color}" fill-opacity=".35" stroke="{color}" stroke-width="1.2"/>'
        f'<circle r="{2.2 * s}" cx="{-2 * s}" fill="{color}"/></g>'
    )


# ------------------------------------------------------------------------------- hero banner
def hero() -> str:
    W, H, u = 1200, 360, "h"
    orbit = Orbit(cx=935, cy=172, scale=118, period=20)
    cloud = orbit_cloud(orbit, fibonacci_sphere(300), radius=2.3)
    ring = (
        f'<ellipse cx="{orbit.cx}" cy="{orbit.cy}" rx="{1.75 * orbit.scale:.1f}" ry="{1.75 * orbit.scale * math.sin(orbit.tilt):.1f}" '
        f'fill="none" stroke="{P["violet"]}" stroke-opacity=".28" stroke-dasharray="2 6"/>'
    )
    shadow = f'<ellipse cx="{orbit.cx}" cy="{orbit.cy + 135}" rx="140" ry="14" fill="url(#{u}g1)" opacity=".7"/>'
    cams = "".join(
        camera_icon(orbit, 1.75 * math.sin(a), 0.0, 1.75 * math.cos(a), c)
        for a, c in ((0.4, P["cyan"]), (2.5, P["violet"]), (4.6, P["pink"]))
    )
    glows = (
        f'<circle cx="940" cy="170" r="260" fill="url(#{u}g1)"><animate attributeName="opacity" values=".7;1;.7" dur="7s" repeatCount="indefinite"/></circle>'
        f'<circle cx="160" cy="40" r="300" fill="url(#{u}g2)"><animate attributeName="opacity" values="1;.6;1" dur="9s" repeatCount="indefinite"/></circle>'
    )
    x0 = 64
    text = (
        f'<circle cx="{x0 + 5}" cy="76" r="5" fill="#34d399"><animate attributeName="opacity" values="1;.25;1" dur="2s" repeatCount="indefinite"/></circle>'
        + mono_text(x0 + 20, 81, "dangaura-tech  ·  Abu Dhabi, UAE", 14, P["soft"])
        + f'<defs><linearGradient id="{u}name" x1="0" x2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#c4bcff"/></linearGradient></defs>'
        f'<text x="{x0 - 2}" y="146" font-family="{SANS}" font-size="54" font-weight="700" fill="url(#{u}name)" letter-spacing="-.5">Dang Truong Minh Le</text>'
        f'<text x="{x0}" y="186" font-family="{SANS}" font-size="22" fill="{P["soft"]}">AI Researcher &amp; Engineer at '
        f'<tspan fill="{P["text"]}" font-weight="600">MBZUAI</tspan></text>'
        f'<rect x="{x0}" y="204" width="64" height="3" rx="1.5" fill="url(#{u}edge)"/>'
        + typed_lines(
            x0,
            246,
            ["> multimodal learning", "> vision-language models (VLMs / MLLMs)", "> 3D vision & scene reconstruction"],
            19,
            [P["violet"], P["cyan"], P["pink"]],
            13.5,
            f"{u}ty",
        )
    )
    x, chips = x0, []
    for label, color in (("Multimodal", P["violet"]), ("VLMs", P["cyan"]), ("3D Vision", P["pink"]),
                         ("Video Tracking", P["amber"]), ("Trustworthy AI", "#34d399")):  # fmt: skip
        s, w = pill(x, 284, label, color, size=13)
        chips.append(s)
        x += w + 10
    body = backdrop(W, H, u) + f'<g clip-path="url(#{u}clip)">{glows}</g>' + ring + shadow + cams + cloud + text + "".join(chips) + frame_edge(W, H, u)
    return svg(W, H, body, "Dang Truong Minh Le - AI Researcher & Engineer at MBZUAI")


# --------------------------------------------------------------------------- footer scene
def scene_points(rng: random.Random):
    floor, table, chair, lamp = [], [], [], []
    for _ in range(150):
        r, a = 1.32 * math.sqrt(rng.random()), rng.random() * 2 * math.pi
        floor.append((r * math.cos(a), -0.78, r * math.sin(a)))
    tx, tz = 0.42, 0.12
    for _ in range(80):
        r, a = 0.42 * math.sqrt(rng.random()), rng.random() * 2 * math.pi
        table.append((tx + r * math.cos(a), -0.12, tz + r * math.sin(a)))
    for _ in range(18):
        table.append((tx + rng.gauss(0, 0.02), -0.12 - rng.random() * 0.66, tz + rng.gauss(0, 0.02)))
    cx, cz = -0.62, 0.42
    for _ in range(45):
        chair.append((cx + rng.uniform(-0.2, 0.2), -0.38, cz + rng.uniform(-0.2, 0.2)))
    for _ in range(35):
        chair.append((cx - 0.2, -0.38 + rng.random() * 0.5, cz + rng.uniform(-0.2, 0.2)))
    for dx in (-0.18, 0.18):
        for dz in (-0.18, 0.18):
            for _ in range(4):
                chair.append((cx + dx, -0.38 - rng.random() * 0.4, cz + dz))
    lx, lz = -0.15, -0.72
    for i in range(22):
        lamp.append((lx, -0.78 + i * 0.055, lz))
    for x, y, z in fibonacci_sphere(46):
        lamp.append((lx + 0.17 * x, 0.52 + 0.14 * y, lz + 0.17 * z))
    return floor, table, chair, lamp


def grounding() -> str:
    W, H, u = 1200, 330, "g"
    orbit = Orbit(cx=900, cy=150, scale=138, period=22)
    floor, table, chair, lamp = scene_points(random.Random(7))
    cycle = 12
    queries = [("a wooden chair", P["amber"], chair), ("the round table", P["pink"], table), ("a desk lamp", P["cyan"], lamp)]
    base = "#5b63a8"

    def group(points, color, i, r=2.4):
        s = i / 3
        kt = [0, s, s + 0.03, s + 0.30, s + 0.33, 1]
        vals = [base, base, color, color, base, base]
        if i == 0:
            kt, vals = kt[1:], vals[1:]
        anim = (
            f'<animate attributeName="fill" dur="{cycle}s" repeatCount="indefinite" '
            f'keyTimes="{";".join(f"{a:.3f}" for a in kt)}" values="{";".join(vals)}"/>'
        )
        return f'<g fill="{base}">{anim}{"".join(orbit.point(x, y, z, r) for x, y, z in points)}</g>'

    cloud = f'<g fill="#3a3f6e">{"".join(orbit.point(x, y, z, 1.7) for x, y, z in floor)}</g>'
    cloud += "".join(group(pts, c, i) for i, (_, c, pts) in enumerate(queries))

    x0 = 56
    title = (
        mono_text(x0, 62, "OPEN-VOCABULARY 3D GROUNDING", 13, P["cyan"], letter_spacing="2")
        + f'<text x="{x0}" y="98" font-family="{SANS}" font-size="28" font-weight="700" fill="{P["text"]}">Ask in words, find it in 3D</text>'
        + f'<text x="{x0}" y="126" font-family="{SANS}" font-size="15" fill="{P["soft"]}">Language features from a vision-language model, fused onto a reconstructed point cloud.</text>'
    )
    term_y = 152
    term = (
        f'<rect x="{x0}" y="{term_y}" width="560" height="62" rx="10" fill="{P["bg0"]}" fill-opacity=".75" stroke="{P["border"]}"/>'
        + "".join(f'<circle cx="{x0 + 18 + i * 14}" cy="{term_y + 14}" r="4" fill="{c}"/>' for i, c in enumerate(("#f87171", "#fbbf24", "#34d399")))
        + mono_text(x0 + 18, term_y + 44, "$ query3d --text", 16, P["soft"])
        + typed_lines(x0 + 18 + 17 * 16 * 0.6, term_y + 44, [f'"{q}"' for q, _, _ in queries], 16, [c for _, c, _ in queries], cycle, f"{u}q")
    )
    # pipeline: text -> encoder -> fused 3D features
    py = 246
    steps = [("text prompt", P["violet"]), ("CLIP encoder", P["cyan"]), ("3D relevance", P["pink"])]
    pipe, x = [], x0
    for j, (label, color) in enumerate(steps):
        s, w = pill(x, py, label, color, size=13)
        pipe.append(s)
        if j < len(steps) - 1:
            ax = x + w + 6
            pipe.append(
                f'<line x1="{ax}" y1="{py + 13}" x2="{ax + 38}" y2="{py + 13}" stroke="{P["muted"]}" stroke-width="2" stroke-dasharray="4 4">'
                f'<animate attributeName="stroke-dashoffset" values="16;0" dur="1s" repeatCount="indefinite"/></line>'
                f'<path d="M{ax + 38},{py + 8} l7,5 -7,5z" fill="{P["muted"]}"/>'
            )
            x = ax + 56
        else:
            x += w
    # beam from the pipeline end into the cloud
    beam = (
        f'<path d="M{x + 10},{py + 13} C{x + 90},{py + 13} {orbit.cx - 220},{orbit.cy + 40} {orbit.cx - 150},{orbit.cy + 20}" '
        f'fill="none" stroke="url(#{u}edge)" stroke-width="2" stroke-dasharray="6 8" opacity=".6">'
        f'<animate attributeName="stroke-dashoffset" values="56;0" dur="1.6s" repeatCount="indefinite"/></path>'
    )
    glows = (
        f'<circle cx="{orbit.cx}" cy="{orbit.cy + 20}" r="230" fill="url(#{u}g1)" opacity=".8"/>'
        f'<circle cx="80" cy="300" r="260" fill="url(#{u}g2)" opacity=".7"/>'
    )
    body = backdrop(W, H, u) + f'<g clip-path="url(#{u}clip)">{glows}</g>' + title + term + "".join(pipe) + beam + cloud + frame_edge(W, H, u)
    return svg(W, H, body, "Animated open-vocabulary 3D grounding: text queries highlight objects in a rotating point cloud")


# ------------------------------------------------------------------------------ project cards
def mini_structura(cx, cy):
    orbit = Orbit(cx=cx, cy=cy, scale=60, period=16)
    cams = "".join(camera_icon(orbit, 1.6 * math.sin(a), 0.1, 1.6 * math.cos(a), c, 0.8) for a, c in ((0.5, P["cyan"]), (3.4, P["pink"])))
    return cams + orbit_cloud(orbit, fibonacci_sphere(150), radius=1.8)


def mini_occtrack(cx, cy):
    out = [f'<rect x="{cx - 14}" y="{cy - 70}" width="28" height="140" rx="4" fill="{P["border"]}" fill-opacity=".9"/>']
    tracks = [(-50, 1, P["cyan"], 5.0, "1"), (-5, -1, P["pink"], 6.5, "2"), (40, 1, P["amber"], 4.2, "3")]
    behind = []
    for dy, d, color, dur, tid in tracks:
        x_from, x_to = (cx - 95, cx + 75) if d > 0 else (cx + 75, cx - 95)
        y = cy + dy - 14
        g = (
            f'<g><animateTransform attributeName="transform" type="translate" values="{x_from} {y};{x_to} {y}" dur="{dur}s" repeatCount="indefinite"/>'
            f'<rect width="22" height="28" rx="3" fill="{color}" fill-opacity=".14" stroke="{color}" stroke-width="1.6"/>'
            f'<text x="11" y="-4" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{color}">id {tid}</text>'
            f'<line x1="{-26 * d if d > 0 else 48}" y1="14" x2="{-2 if d > 0 else 24}" y2="14" stroke="{color}" stroke-opacity=".5" stroke-dasharray="2 3"/></g>'
        )
        behind.append(g)
    return "".join(behind) + out[0].replace('fill-opacity=".9"', 'fill-opacity=".85"')


def mini_baunet(cx, cy):
    pts = []
    for k in range(48):
        a = 2 * math.pi * k / 48
        r = 52 + 10 * math.sin(3 * a) + 6 * math.cos(5 * a + 1)
        pts.append((cx + r * math.cos(a), cy + 0.9 * r * math.sin(a)))
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{P["amber"]}"><animate attributeName="opacity" values="0;1;0" dur="2.4s" begin="{(i % 6) * 0.4:.1f}s" repeatCount="indefinite"/></circle>'
        for i, (x, y) in enumerate(pts[::4])
    )
    return (
        f'<path d="{d}" fill="{P["violet"]}" fill-opacity=".22"/>'
        f'<path d="{d}" fill="none" stroke="{P["cyan"]}" stroke-width="10" stroke-opacity=".18"><animate attributeName="stroke-width" values="6;16;6" dur="3s" repeatCount="indefinite"/></path>'
        f'<path d="{d}" fill="none" stroke="{P["cyan"]}" stroke-width="2" stroke-dasharray="7 5"><animate attributeName="stroke-dashoffset" values="24;0" dur="1.2s" repeatCount="indefinite"/></path>'
        + dots
    )


def mini_cxr(cx, cy):
    x0, y0, s = cx - 70, cy + 65, 130
    out = [
        f'<line x1="{x0}" y1="{y0}" x2="{x0 + s}" y2="{y0}" stroke="{P["muted"]}"/>'
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 - s}" stroke="{P["muted"]}"/>'
        f'<line x1="{x0}" y1="{y0}" x2="{x0 + s}" y2="{y0 - s}" stroke="{P["soft"]}" stroke-dasharray="4 4" stroke-opacity=".7"/>'
    ]
    n, bw = 6, s / 6
    for i in range(n):
        ideal = (i + 0.5) / n * s
        over = ideal * 0.55 + 4
        x = x0 + i * bw + 3
        vals = f"{over:.1f};{ideal:.1f};{ideal:.1f};{over:.1f}"
        ys = ";".join(f"{y0 - float(v):.1f}" for v in vals.split(";"))
        out.append(
            f'<rect x="{x:.1f}" width="{bw - 6:.1f}" rx="2" fill="{P["violet"]}" fill-opacity=".75">'
            f'<animate attributeName="height" values="{vals}" keyTimes="0;.35;.75;1" dur="5s" repeatCount="indefinite"/>'
            f'<animate attributeName="y" values="{ys}" keyTimes="0;.35;.75;1" dur="5s" repeatCount="indefinite"/></rect>'
        )
    out.append(mono_text(x0 + 4, y0 - s + 4, "reliability", 10, P["muted"]))
    return "".join(out)


def mini_chain(cx, cy):
    out, n, bw, gap = [], 5, 58, 30
    x0 = cx - (n * bw + (n - 1) * gap) / 2
    for i in range(n):
        x = x0 + i * (bw + gap)
        out.append(
            f'<rect x="{x:.1f}" y="{cy - 29}" width="{bw}" height="58" rx="9" fill="{P["bg0"]}" stroke="{P["violet"]}" stroke-width="1.6">'
            f'<animate attributeName="stroke" values="{P["violet"]};{P["amber"]};{P["violet"]}" keyTimes="0;.1;.3" dur="5s" begin="{i}s" repeatCount="indefinite"/></rect>'
            + "".join(f'<rect x="{x + 12:.1f}" y="{cy - 15 + k * 10}" width="{bw - 24 - (k % 2) * 10}" height="4" rx="2" fill="{P["soft"]}" fill-opacity=".45"/>' for k in range(3))
        )
        if i < n - 1:
            lx = x + bw
            out.append(f'<line x1="{lx:.1f}" y1="{cy}" x2="{lx + gap:.1f}" y2="{cy}" stroke="{P["muted"]}" stroke-width="2"/>')
    out.append(
        f'<circle r="6" cy="{cy}" fill="{P["amber"]}"><animate attributeName="cx" values="{x0 - 10:.1f};{x0 + n * bw + (n - 1) * gap + 10:.1f}" dur="5s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.08;.92;1" dur="5s" repeatCount="indefinite"/></circle>'
    )
    return "".join(out)


PROJECTS = [
    dict(slug="structura", name="Structura", area="3D VISION · RECONSTRUCTION", lang=("Python", "#3572A5"),
         lines=["Incremental structure-from-motion with", "self-calibrating bundle adjustment, retrieval", "and open-vocabulary 3D queries."],
         tags=[("SfM", P["cyan"]), ("Retrieval", P["violet"]), ("CLIP", P["pink"])], mini=mini_structura),
    dict(slug="occtrack", name="OccTrack", area="VIDEO UNDERSTANDING · TRACKING", lang=("Python", "#3572A5"),
         lines=["Occlusion-aware multi-object tracking with", "camera-motion compensation, observation-", "centric re-updates and Re-ID memory."],
         tags=[("MOT", P["cyan"]), ("Kalman", P["violet"]), ("HOTA", P["pink"])], mini=mini_occtrack),
    dict(slug="bau-net", name="BAU-Net", area="DENSE PREDICTION · UNCERTAINTY", lang=("Python", "#3572A5"),
         lines=["Boundary- and uncertainty-aware segmentation", "with a transformer bottleneck and", "uncertainty-guided point refinement."],
         tags=[("Segmentation", P["cyan"]), ("SDF loss", P["violet"]), ("ONNX", P["pink"])], mini=mini_baunet),
    dict(slug="cxr-trust", name="CXR-Trust", area="TRUSTWORTHY RECOGNITION", lang=("Python", "#3572A5"),
         lines=["Calibrated, explainable chest X-ray", "classification with conformal guarantees,", "Grad-CAM++ and a zero-shot VLM baseline."],
         tags=[("Conformal", P["cyan"]), ("Grad-CAM++", P["violet"]), ("BiomedCLIP", P["pink"])], mini=mini_cxr),
    dict(slug="chainvault", name="ChainVault", area="BLOCKCHAIN · SOLIDITY", lang=("Solidity", "#AA6746"), wide=True,
         lines=["ERC-20 governance token, reward-streaming staking vault and token vesting,", "governed on-chain through an OpenZeppelin Governor behind a timelock."],
         tags=[("Solidity", P["cyan"]), ("Hardhat", P["violet"]), ("Governor", P["pink"]), ("ERC20Votes", P["amber"])], mini=mini_chain),
]  # fmt: skip


def project_card(p: dict) -> str:
    wide = p.get("wide", False)
    W, H, u = (1220, 270, "c") if wide else (600, 270, "c")
    x0 = 34
    head = (
        mono_text(x0, 50, p["area"], 12, P["cyan"], letter_spacing="1.5")
        + f'<text x="{x0}" y="88" font-family="{SANS}" font-size="31" font-weight="700" fill="{P["text"]}">{escape(p["name"])}</text>'
    )
    desc = "".join(
        f'<text x="{x0}" y="{120 + i * 22}" font-family="{SANS}" font-size="15" fill="{P["soft"]}">{escape(t)}</text>'
        for i, t in enumerate(p["lines"])
    )
    x, tags = x0, []
    ty = 120 + len(p["lines"]) * 22 + 2
    for label, color in p["tags"]:
        s, w = pill(x, ty, label, color, size=12)
        tags.append(s)
        x += w + 8
    lang, lc = p["lang"]
    foot = (
        f'<circle cx="{x0 + 6}" cy="{H - 26}" r="6" fill="{lc}"/>'
        f'<text x="{x0 + 20}" y="{H - 21}" font-family="{SANS}" font-size="13" fill="{P["soft"]}">{lang}</text>'
        + mono_text(x0 + 100, H - 21, f"github.com/dangaura-tech/{p['slug']}", 12, P["muted"])
    )
    mini = p["mini"](W - 140 if not wide else W - 290, 128)
    body = backdrop(W, H, u, rx=14) + f'<circle cx="{W - 140}" cy="110" r="150" fill="url(#{u}g1)" opacity=".55"/>' + head + desc + "".join(tags) + foot + mini + frame_edge(W, H, u, rx=14)
    return svg(W, H, body, f"{p['name']}: {' '.join(p['lines'])}")


def divider() -> str:
    W, H, u = 1200, 14, "d"
    return svg(
        W,
        H,
        f'<defs><linearGradient id="{u}" x1="0" x2="1"><stop offset="0" stop-color="{P["violet"]}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="{P["cyan"]}"/><stop offset="1" stop-color="{P["pink"]}" stop-opacity="0"/></linearGradient></defs>'
        f'<rect y="6" width="{W}" height="2" fill="url(#{u})" opacity=".6"/>'
        f'<circle cy="7" r="3.5" fill="{P["cyan"]}"><animate attributeName="cx" values="0;{W}" dur="6s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.15;.85;1" dur="6s" repeatCount="indefinite"/></circle>',
        "divider",
    )


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    (ROOT / "hero.svg").write_text(hero())
    (ROOT / "grounding.svg").write_text(grounding())
    (ROOT / "divider.svg").write_text(divider())
    for p in PROJECTS:
        (ROOT / f"card-{p['slug']}.svg").write_text(project_card(p))
    for f in sorted(ROOT.glob("*.svg")):
        print(f"{f.name:28s} {f.stat().st_size / 1024:7.1f} KB")


if __name__ == "__main__":
    main()
