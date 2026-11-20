"""Conservative break locus from measured S1/S2 flow (L/min)."""

from __future__ import annotations

from typing import Any

ABS_LOSS_MIN_LPM = 1.8
REL_LOSS_FRAC = 0.20
MIN_QIN_LPM = 2.0


def estimate_break(
    inlet_lpm: float,
    outlet_lpm: float,
    *,
    length_m: float = 50.0,
) -> dict[str, Any]:
    qin = round(float(inlet_lpm or 0.0), 2)
    qout = round(float(outlet_lpm or 0.0), 2)
    loss = round(max(qin - qout, 0.0), 2)
    need = round(max(ABS_LOSS_MIN_LPM, REL_LOSS_FRAC * qin), 2)
    length = float(length_m) if length_m and length_m > 0 else 50.0

    base: dict[str, Any] = {
        "available": False,
        "qin_lpm": qin,
        "qout_lpm": qout,
        "loss_lpm": loss,
        "loss_threshold_lpm": need,
        "length_m": length,
        "distance_from_s1_m": None,
        "distance_from_s2_m": None,
        "distance_from_s1_range_m": None,
        "severity_pct": round(min(100.0, (loss / max(qin, 0.01)) * 100.0), 1) if qin > 0 else 0.0,
        "band": None,
        "band_label": None,
        "confidence": "none",
        "summary": "",
    }

    if qin < MIN_QIN_LPM:
        base["summary"] = f"Qin {qin:.2f} L/min below {MIN_QIN_LPM:.1f} — no locus"
        return base
    if loss < need:
        base["summary"] = f"Loss {loss:.2f} below threshold {need:.2f} L/min — no locus"
        return base

    severity = min(1.0, loss / max(qin, 0.01))
    if severity >= 0.40:
        band, label, conf = "near_s1", "near inlet (S1)", "medium"
        frac_lo, frac_hi = 0.05, 0.35
    elif severity >= 0.18:
        band, label, conf = "mid", "mid-segment", "medium"
        frac_lo, frac_hi = 0.30, 0.70
    else:
        band, label, conf = "near_s2", "near outlet (S2)", "low"
        frac_lo, frac_hi = 0.55, 0.95

    s1_lo = round(length * frac_lo, 1)
    s1_hi = round(length * frac_hi, 1)
    s1_mid = round((s1_lo + s1_hi) / 2.0, 1)
    s2_mid = round(max(length - s1_mid, 0.0), 1)

    base.update(
        {
            "available": True,
            "band": band,
            "band_label": label,
            "confidence": conf,
            "distance_from_s1_m": s1_mid,
            "distance_from_s2_m": s2_mid,
            "distance_from_s1_range_m": [s1_lo, s1_hi],
            "summary": (
                f"Leak ~{s1_mid:.0f}m from S1 / ~{s2_mid:.0f}m from S2 "
                f"({label}, loss {loss:.2f} L/min)"
            ),
        }
    )
    return base
