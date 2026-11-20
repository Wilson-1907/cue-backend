"""Build leak SMS text that pinpoints the repair area."""

from __future__ import annotations

from typing import Any


def format_leak_sms(
    *,
    zone: str,
    inlet: float,
    outlet: float,
    locus: dict[str, Any] | None = None,
    from_s1_m: float | None = None,
    from_s2_m: float | None = None,
    severity_pct: float | None = None,
    length_m: float = 50.0,
) -> str:
    loss = max(float(inlet) - float(outlet), 0.0)
    length = float(length_m) if length_m and length_m > 0 else 50.0
    loc = locus or {}

    s1 = from_s1_m if from_s1_m is not None else loc.get("distance_from_s1_m")
    s2 = from_s2_m if from_s2_m is not None else loc.get("distance_from_s2_m")
    sev = severity_pct if severity_pct is not None else loc.get("severity_pct")
    band = loc.get("band_label") or loc.get("band") or ""
    conf = loc.get("confidence") or ""
    rng = loc.get("distance_from_s1_range_m")

    lines = [
        f"CUE LEAK {zone}",
        "--- LEAK LOCATION ---",
    ]

    if s1 is not None and s2 is not None:
        lines.append(f"PIN: ~{float(s1):.0f}m from S1 / ~{float(s2):.0f}m from S2")
    if rng and len(rng) == 2:
        s1_lo, s1_hi = float(rng[0]), float(rng[1])
        s2_lo = max(length - s1_hi, 0.0)
        s2_hi = max(length - s1_lo, 0.0)
        lines.append(f"SEARCH: {s1_lo:.0f}-{s1_hi:.0f}m from inlet S1")
        lines.append(f"        ({s2_lo:.0f}-{s2_hi:.0f}m from outlet S2)")
    elif s1 is not None:
        half = max(length * 0.12, 2.0)
        lo = max(float(s1) - half, 0.0)
        hi = min(float(s1) + half, length)
        lines.append(f"SEARCH: {lo:.0f}-{hi:.0f}m from inlet S1")

    if band:
        lines.append(f"BAND: {band}")
    if sev is not None:
        lines.append(f"SEVERITY: {float(sev):.0f}% loss")
    if conf and conf != "none":
        lines.append(f"CONF: {conf}")

    lines.append(f"PIPE: {length:.0f}m S1(in)->S2(out)")
    lines.append("--- FLOW ---")
    lines.append(f"In {float(inlet):.2f} L/min")
    lines.append(f"Out {float(outlet):.2f} L/min")
    lines.append(f"Loss {loss:.2f} L/min")
    lines.append("ACTION: Valve CLOSED. Inspect PIN/SEARCH section.")
    return "\n".join(lines)
