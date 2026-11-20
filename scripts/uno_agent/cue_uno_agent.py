#!/usr/bin/env python3
"""
CUE Uno Agent — USB bridge locked to COM10.

Posts the same kit telemetry to every configured API target
(e.g. Render cloud + localhost) so online and local dashboards stay in sync.
Never scans Bluetooth/AMT/other COM ports.
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
from typing import Any

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("cue_uno_agent")

# Per-target: None=unknown, True=disconnect API works, False=old server
_OFFLINE_API_OK: dict[str, bool | None] = {}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        example = HERE / "config.example.json"
        raise SystemExit(
            f"Missing {CONFIG_PATH}. Copy {example.name} -> config.json and fill targets."
        )
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    targets: list[dict[str, Any]] = []
    if isinstance(raw.get("targets"), list) and raw["targets"]:
        for t in raw["targets"]:
            if not t.get("api_base") or not t.get("api_key") or not t.get("device_id"):
                raise SystemExit("Each targets[] entry needs api_base, device_id, api_key")
            targets.append(
                {
                    "name": t.get("name") or t["api_base"],
                    "api_base": str(t["api_base"]).rstrip("/"),
                    "device_id": t["device_id"],
                    "api_key": t["api_key"],
                    "valve_id": int(t.get("valve_id") or raw.get("valve_id") or 1),
                    "enabled": t.get("enabled", True),
                }
            )
    else:
        if not raw.get("api_base") or not raw.get("api_key") or not raw.get("device_id"):
            raise SystemExit("config.json needs api_base/device_id/api_key or targets[]")
        targets.append(
            {
                "name": "primary",
                "api_base": str(raw["api_base"]).rstrip("/"),
                "device_id": raw["device_id"],
                "api_key": raw["api_key"],
                "valve_id": int(raw.get("valve_id") or 1),
                "enabled": True,
            }
        )

    cfg = {
        "port": (raw.get("port") or "COM10").strip() or "COM10",
        "baud": int(raw.get("baud") or 9600),
        "sensor_inlet": raw.get("sensor_inlet") or "S1",
        "sensor_outlet": raw.get("sensor_outlet") or "S2",
        "scan_interval_sec": float(raw.get("scan_interval_sec") or 2),
        "targets": [t for t in targets if t.get("enabled", True)],
        "_valve_id": int(raw.get("valve_id") or 1),
    }
    if not cfg["targets"]:
        raise SystemExit("No enabled API targets in config.json")
    return cfg


def headers(target: dict) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Device-Id": target["device_id"],
        "X-Api-Key": target["api_key"],
    }


def port_present(port: str) -> bool:
    want = port.upper().strip()
    for p in list_ports.comports():
        if (p.device or "").upper() == want:
            return True
    return False


def probe_port(port: str, baud: int, timeout: float = 2.0) -> bool:
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
            return True
    except Exception:
        return False


def find_uno_port(cfg: dict) -> str | None:
    forced = cfg["port"]
    if not port_present(forced):
        log.info("Locked port %s not present", forced)
        return None
    # Listed as present — open in session_on_port (separate probe can false-fail if busy)
    log.info("Using locked port %s", forced)
    return forced


def _post_one(
    target: dict, path: str, payload: dict, timeout: float = 12
) -> requests.Response | None:
    url = target["api_base"] + path
    try:
        r = requests.post(url, headers=headers(target), json=payload, timeout=timeout)
        if r.status_code >= 400:
            log.warning(
                "[%s] POST %s -> %s %s",
                target["name"],
                path,
                r.status_code,
                r.text[:160],
            )
        return r
    except Exception as exc:
        log.warning("[%s] POST %s failed: %s", target["name"], path, exc)
        return None


def _get_one(target: dict, path: str, timeout: float = 10) -> requests.Response | None:
    url = target["api_base"] + path
    try:
        r = requests.get(url, headers=headers(target), timeout=timeout)
        if r.status_code >= 400:
            log.warning(
                "[%s] GET %s -> %s %s",
                target["name"],
                path,
                r.status_code,
                r.text[:160],
            )
        return r
    except Exception as exc:
        log.warning("[%s] GET %s failed: %s", target["name"], path, exc)
        return None


def fanout_post(cfg: dict, path: str, payload: dict, timeout: float = 12) -> None:
    for target in cfg["targets"]:
        _post_one(target, path, payload, timeout=timeout)


def post_reading(
    cfg: dict, sensor_id: str, flow: Decimal, volume: Decimal, pulse: int
) -> None:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for target in cfg["targets"]:
        payload = {
            "device_id": target["device_id"],
            "sensor_id": sensor_id,
            "flow_rate": str(flow),
            "volume": str(volume),
            "pulse_count": pulse,
            "timestamp": ts,
        }
        _post_one(target, "/iot/readings/", payload, timeout=15)


def post_warning(cfg: dict, title: str, message: str, severity: str = "CRITICAL") -> None:
    fanout_post(
        cfg,
        "/iot/devices/warnings/",
        {"title": title, "message": message, "severity": severity},
    )


def report_valve_status(cfg: dict, status: str) -> None:
    status = status.upper().strip()
    if status not in {"OPEN", "CLOSED"}:
        return
    for target in cfg["targets"]:
        vid = int(target.get("valve_id") or cfg.get("_valve_id") or 1)
        cfg["_valve_id"] = vid
        _post_one(target, f"/iot/valves/{vid}/status/", {"status": status})


def report_offline(cfg: dict, note: str = "COM port disconnected") -> None:
    """Mark kit offline on every target that supports disconnect heartbeats."""
    for target in cfg["targets"]:
        key = target["api_base"]
        if _OFFLINE_API_OK.get(key) is False:
            continue
        r = _post_one(
            target,
            "/iot/heartbeat/",
            {
                "device_id": target["device_id"],
                "status": "DISCONNECTED",
                "firmware_version": "uno-agent",
            },
        )
        if r is None:
            continue
        try:
            body = r.json() if r.content else {}
            conn = (body.get("data") or {}).get("connection_status")
            if conn == "DISCONNECTED" or "Disconnect" in (body.get("message") or ""):
                _OFFLINE_API_OK[key] = True
                _post_one(
                    target,
                    "/iot/devices/status/",
                    {"status": "DISCONNECTED", "note": note},
                )
                log.info("[%s] Reported OFFLINE (%s)", target["name"], note)
                continue
        except Exception:
            pass
        _OFFLINE_API_OK[key] = False
        log.warning(
            "[%s] disconnect heartbeat not supported yet — relying on timeout (%s)",
            target["name"],
            note,
        )


def heartbeat_ok(cfg: dict) -> None:
    for target in cfg["targets"]:
        _post_one(
            target,
            "/iot/heartbeat/",
            {
                "device_id": target["device_id"],
                "status": "OK",
                "firmware_version": "uno-agent",
            },
        )


def poll_valve_commands(cfg: dict, ser: serial.Serial) -> None:
    """Pull pending commands from every target; first success wins per command id."""
    seen: set[Any] = set()
    for target in cfg["targets"]:
        r = _get_one(target, "/iot/commands/pending/")
        if r is None or r.status_code >= 400:
            continue
        try:
            body = r.json()
        except Exception:
            continue
        data = body.get("data") or body
        cmds = (data or {}).get("commands") or []
        for cmd in cmds:
            cid = cmd.get("id")
            action = (cmd.get("command_type") or "").upper()
            if not cid or cid in seen or action not in {"CLOSE", "OPEN"}:
                continue
            seen.add(cid)
            if cmd.get("valve_id"):
                cfg["_valve_id"] = int(cmd["valve_id"])
            _post_one(target, f"/iot/commands/{cid}/acknowledge/", {})
            line = "CLOSE" if action == "CLOSE" else "RESET"
            try:
                ser.write((line + "\r\n").encode())
                ser.flush()
                log.info("[%s] TX %s (command %s)", target["name"], line, cid)
            except Exception:
                log.exception("serial TX failed for command %s", cid)
                _post_one(
                    target,
                    f"/iot/commands/{cid}/execute/",
                    {"success": False, "message": "Serial write failed"},
                )
                continue
            ok = False
            for _ in range(2):
                resp = _post_one(
                    target,
                    f"/iot/commands/{cid}/execute/",
                    {"success": True, "message": f"Sent {line} to Uno"},
                )
                if resp is not None and resp.status_code < 400:
                    ok = True
                    break
                time.sleep(1.2)
            if ok:
                report_valve_status(cfg, "CLOSED" if action == "CLOSE" else "OPEN")
            else:
                log.error("execute confirm failed for command %s", cid)


def session_on_port(cfg: dict, port: str) -> None:
    baud = int(cfg["baud"])
    vol_in = Decimal("0")
    vol_out = Decimal("0")
    pulse = 0
    pending_leak = None
    pending_estimate = None
    last_cmd_poll = 0.0
    last_heartbeat = 0.0

    with serial.Serial(port, baud, timeout=0.25) as ser:
        names = ", ".join(t["name"] for t in cfg["targets"])
        log.info("Connected %s @ %s — streaming to: %s", port, baud, names)
        heartbeat_ok(cfg)
        last_heartbeat = time.time()

        while True:
            now = time.time()
            if now - last_heartbeat >= 25.0:
                heartbeat_ok(cfg)
                last_heartbeat = now
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

            up = text.upper()
            if "ACK:RESET" in up or "WATER VALVE OPEN" in up or up.endswith("VALVE OPEN"):
                report_valve_status(cfg, "OPEN")
            elif "ACK:VALVE_CLOSED" in up or "WATER VALVE CLOSED" in up or "VALVE_CLOSED" in up:
                report_valve_status(cfg, "CLOSED")

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
                    f"Zone {pending_leak['zone']} inlet={pending_leak['inlet']} "
                    f"outlet={pending_leak['outlet']}",
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
                log.exception("post readings failed — keep listening")


def main() -> None:
    cfg = load_config()
    locked = cfg["port"]
    log.info("CUE Uno Agent starting (locked %s only). Config=%s", locked, CONFIG_PATH)
    for t in cfg["targets"]:
        log.info("Target %-10s %s device=%s", t["name"], t["api_base"], t["device_id"])
    scan = float(cfg["scan_interval_sec"])
    was_online = False
    last_offline_post = 0.0

    while True:
        try:
            port = find_uno_port(cfg)
            if not port:
                now = time.time()
                if was_online or (now - last_offline_post) >= 30.0:
                    log.warning("%s missing — reporting OFFLINE", locked)
                    report_offline(cfg, f"{locked} not present")
                    last_offline_post = now
                    was_online = False
                else:
                    log.info(
                        "Waiting for %s only (not scanning other COM ports). Retry in %.0fs",
                        locked,
                        scan,
                    )
                time.sleep(scan)
                continue
            try:
                was_online = True
                session_on_port(cfg, port)
            except serial.SerialException as exc:
                log.warning("%s disconnected (%s) — reporting OFFLINE", port, exc)
                report_offline(cfg, f"{port} disconnected: {exc}")
                was_online = False
                last_offline_post = time.time()
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
