#!/usr/bin/env python3
"""
CUE Uno Agent — always-on USB bridge for Contabo / any CUE API host.

- Watches for Arduino/Uno (or any serial adapter) on ANY COM port
- Auto-connects when you plug the cable in
- Reconnects forever if unplugged / port changes
- Posts flow readings + valve commands to the CUE HTTP API

Run once at login (see install_windows_autostart.ps1).
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    raise SystemExit(1)

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("pip install pyserial", file=sys.stderr)
    raise SystemExit(1)

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
LOG_PATH = HERE / "uno_agent.log"

FLOW_RE = re.compile(
    r"Inlet \(S1\):\s*(?P<inlet>[-+]?\d*\.?\d+)\s*L/min\s*\|\s*"
    r"Outlet \(S2\):\s*(?P<outlet>[-+]?\d*\.?\d+)\s*L/min",
    re.I,
)
DV_RE = re.compile(
    r"dV_in:(?P<din>[-+]?\d*\.?\d+)mL\s+dV_out:(?P<dout>[-+]?\d*\.?\d+)mL",
    re.I,
)
LEAK_RE = re.compile(
    r"^LEAK_ALERT:(?P<zone>[A-Za-z0-9_]+):(?P<inlet>[-+]?\d*\.?\d+):(?P<outlet>[-+]?\d*\.?\d+)\s*$"
)
ESTIMATE_RE = re.compile(
    r"^ESTIMATE:(?P<s1>[-+]?\d*\.?\d+):(?P<s2>[-+]?\d*\.?\d+):(?P<sev>[-+]?\d*\.?\d+)"
    r":(?P<length>[-+]?\d*\.?\d+):(?P<loss>[-+]?\d*\.?\d+)"
    r":(?P<qin>[-+]?\d*\.?\d+):(?P<qout>[-+]?\d*\.?\d+):(?P<band>\d+)\s*$"
)

# Common Arduino / USB-serial chip vendor IDs
ARDUINO_VIDS = {
    0x2341,  # Arduino
    0x2A03,  # Arduino.org
    0x1A86,  # CH340
    0x0403,  # FTDI
    0x10C4,  # CP210x
    0x067B,  # Prolific
}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("cue_uno_agent")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        example = HERE / "config.example.json"
        raise SystemExit(
            f"Missing {CONFIG_PATH}. Copy {example.name} → config.json and fill api_base + api_key."
        )
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not cfg.get("api_base") or not cfg.get("api_key") or not cfg.get("device_id"):
        raise SystemExit("config.json needs api_base, device_id, and api_key")
    cfg["api_base"] = cfg["api_base"].rstrip("/")
    cfg.setdefault("baud", 9600)
    cfg.setdefault("sensor_inlet", "S1")
    cfg.setdefault("sensor_outlet", "S2")
    cfg.setdefault("scan_interval_sec", 2)
    cfg.setdefault("prefer_vid", True)
    return cfg


def headers(cfg: dict) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Device-Id": cfg["device_id"],
        "X-Api-Key": cfg["api_key"],
    }


def list_candidate_ports(prefer_vid: bool = True) -> list[str]:
    ports = list(list_ports.comports())
    if not ports:
        return []
    scored: list[tuple[int, str]] = []
    for p in ports:
        score = 0
        desc = f"{p.description or ''} {p.manufacturer or ''} {p.product or ''}".lower()
        if prefer_vid and p.vid and int(p.vid) in ARDUINO_VIDS:
            score += 100
        if any(k in desc for k in ("arduino", "ch340", "uno", "usb serial", "cp210", "ftdi")):
            score += 50
        if p.device:
            scored.append((score, p.device))
    scored.sort(key=lambda x: (-x[0], x[1]))
    # Prefer high-score first, but still try all ports
    ordered = [d for _, d in scored]
    # Deduplicate
    seen = set()
    out = []
    for d in ordered:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def probe_port(port: str, baud: int, timeout: float = 2.5) -> bool:
    """Open briefly; treat success as usable (firmware may be quiet until flow)."""
    try:
        with serial.Serial(port, baud, timeout=0.3) as ser:
            deadline = time.time() + timeout
            while time.time() < deadline:
                raw = ser.readline()
                if not raw:
                    continue
                text = raw.decode("utf-8", errors="replace")
                if FLOW_RE.search(text) or "S1" in text or "Inlet" in text or "CUE" in text.upper():
                    return True
            # Port opened OK even if quiet — accept as candidate if VID matched earlier
            return True
    except Exception:
        return False


def find_uno_port(cfg: dict) -> str | None:
    candidates = list_candidate_ports(cfg.get("prefer_vid", True))
    if not candidates:
        return None
    # If user locked a port and it exists, try it first
    forced = (cfg.get("port") or "").strip()
    if forced and forced in candidates:
        candidates = [forced] + [c for c in candidates if c != forced]
    for port in candidates:
        log.info("Probing %s …", port)
        if probe_port(port, int(cfg["baud"])):
            return port
    # Last resort: first available COM
    return candidates[0] if candidates else None


def post_reading(cfg: dict, sensor_id: str, flow: Decimal, volume: Decimal, pulse: int) -> None:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "device_id": cfg["device_id"],
        "sensor_id": sensor_id,
        "flow_rate": str(flow),
        "volume": str(volume),
        "pulse_count": pulse,
        "timestamp": ts,
    }
    url = cfg["api_base"] + "/iot/readings/"
    r = requests.post(url, headers=headers(cfg), json=payload, timeout=15)
    if r.status_code >= 400:
        log.warning("reading POST %s → %s %s", sensor_id, r.status_code, r.text[:200])


def post_warning(cfg: dict, title: str, message: str, severity: str = "CRITICAL") -> None:
    url = cfg["api_base"] + "/iot/devices/warnings/"
    try:
        requests.post(
            url,
            headers=headers(cfg),
            json={"title": title, "message": message, "severity": severity},
            timeout=15,
        )
    except Exception:
        log.exception("warning POST failed")


def poll_valve_commands(cfg: dict, ser: serial.Serial) -> None:
    url = cfg["api_base"] + "/iot/commands/pending/"
    try:
        r = requests.get(url, headers=headers(cfg), timeout=10)
        if r.status_code >= 400:
            return
        body = r.json()
        data = body.get("data") or body
        cmds = (data or {}).get("commands") or []
        for cmd in cmds:
            action = (cmd.get("command_type") or "").upper()
            cid = cmd.get("id")
            if action not in {"CLOSE", "OPEN"} or not cid:
                continue
            line = "CLOSE" if action == "CLOSE" else "RESET"
            ser.write((line + "\r\n").encode())
            ser.flush()
            log.info("TX %s (command %s)", line, cid)
            requests.post(
                cfg["api_base"] + f"/iot/commands/{cid}/execute/",
                headers=headers(cfg),
                json={"success": True, "message": f"Sent {line} to Uno"},
                timeout=10,
            )
    except Exception:
        log.exception("valve poll failed")


def session_on_port(cfg: dict, port: str) -> None:
    baud = int(cfg["baud"])
    vol_in = Decimal("0")
    vol_out = Decimal("0")
    pulse = 0
    pending_leak = None
    pending_estimate = None
    last_cmd_poll = 0.0

    with serial.Serial(port, baud, timeout=0.25) as ser:
        log.info("Connected %s @ %s — streaming to %s", port, baud, cfg["api_base"])
        # Heartbeat
        try:
            requests.post(
                cfg["api_base"] + "/iot/heartbeat/",
                headers=headers(cfg),
                json={"device_id": cfg["device_id"], "status": "OK", "firmware_version": "uno-agent"},
                timeout=10,
            )
        except Exception:
            log.exception("heartbeat failed")

        while True:
            now = time.time()
            if now - last_cmd_poll > 2.0:
                poll_valve_commands(cfg, ser)
                last_cmd_poll = now

            raw = ser.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            log.info("SERIAL: %s", text.encode("ascii", "replace").decode("ascii"))

            est = ESTIMATE_RE.match(text)
            if est:
                pending_estimate = est.groupdict()
                if pending_leak:
                    msg = (
                        f"Zone {pending_leak['zone']} inlet={pending_leak['inlet']} "
                        f"outlet={pending_leak['outlet']} estimate={pending_estimate}"
                    )
                    post_warning(cfg, "LEAK_ALERT from Uno", msg, "CRITICAL")
                    pending_leak = None
                    pending_estimate = None
                continue

            leak = LEAK_RE.match(text)
            if leak:
                pending_leak = {
                    "zone": leak.group("zone"),
                    "inlet": leak.group("inlet"),
                    "outlet": leak.group("outlet"),
                }
                continue

            m = FLOW_RE.search(text)
            if not m:
                if pending_leak and text.startswith("REPAIR:"):
                    post_warning(
                        cfg,
                        "LEAK_ALERT from Uno",
                        f"Zone {pending_leak['zone']} (no estimate)",
                        "CRITICAL",
                    )
                    pending_leak = None
                continue

            if pending_leak:
                post_warning(
                    cfg,
                    "LEAK_ALERT from Uno",
                    f"Zone {pending_leak['zone']} inlet={pending_leak['inlet']} outlet={pending_leak['outlet']}",
                    "CRITICAL",
                )
                pending_leak = None
                pending_estimate = None

            inlet = Decimal(m.group("inlet"))
            outlet = Decimal(m.group("outlet"))
            din = dout = Decimal("0")
            dv = DV_RE.search(text)
            if dv:
                din = Decimal(dv.group("din"))
                dout = Decimal(dv.group("dout"))
                if din < 4:
                    din = Decimal("0")
                if dout < 4:
                    dout = Decimal("0")
            vol_in += din / Decimal("1000")
            vol_out += dout / Decimal("1000")
            pulse += 1
            try:
                post_reading(cfg, cfg["sensor_inlet"], inlet, vol_in, pulse)
                post_reading(cfg, cfg["sensor_outlet"], outlet, vol_out, pulse)
            except Exception:
                log.exception("post readings failed — will keep listening")


def main() -> None:
    cfg = load_config()
    log.info("CUE Uno Agent starting (auto any-port). Config=%s", CONFIG_PATH)
    log.info("API=%s device=%s", cfg["api_base"], cfg["device_id"])
    scan = float(cfg.get("scan_interval_sec", 2))

    while True:
        try:
            port = find_uno_port(cfg)
            if not port:
                log.info("No serial device yet — plug in the Uno (any USB port). Retry in %.0fs", scan)
                time.sleep(scan)
                continue
            try:
                session_on_port(cfg, port)
            except serial.SerialException as exc:
                log.warning("%s disconnected (%s) — waiting for plug…", port, exc)
                time.sleep(scan)
            except KeyboardInterrupt:
                log.info("Stopped by user")
                break
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("agent loop error")
            time.sleep(scan)


if __name__ == "__main__":
    main()
