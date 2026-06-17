"""The industrial domain's tools: CAN/ISOBUS edge decode + diagnostics.

All five are offline and deterministic — same input, same output, no network —
which is what makes the eval reproducible and keyless. Decode ground-truth comes
from the public-standard signal subset (codec / signals.json); the bus logs are
the committed synthetic corpus under fixtures/industrial/logs/.

`safety_bound_check` is the deterministic rules tool: it never asks a model, it
just compares a value to a published operational bound. It is the HARD gate — an
edge agent must never wave through an out-of-range actuation.
"""

from __future__ import annotations

import itertools
import json
from typing import Any

from agentic_eval.domains.industrial import codec

LOGS_DIR = codec.SIGNALS_PATH.parent / "logs"

# fault-model thresholds (documented in README; the generator injects to these)
STUCK_MIN_SAMPLES = 5
DRIFT_MIN_SAMPLES = 4
DRIFT_DELTA = 8.0
FUSION_TOL_KMH = 1.0

_DB = codec.load_db()
_SIGNAL_INDEX: dict[str, tuple[codec.Message, codec.Signal]] = {
    sig.name: (msg, sig) for msg in _DB.values() for sig in msg.signals
}


class ToolError(ValueError):
    """Raised on invalid tool input; returned to the model as is_error."""


def _is_proprietary_pgn(pgn: int) -> bool:
    """SAE J1939 / ISO 11783 proprietary ranges (opendbc-ag scope policy)."""
    lo = pgn & 0x3FFFF
    return lo == 0xEF00 or 0xFF00 <= lo <= 0xFFFF or lo == 0x1EF00 or 0x1FF00 <= lo <= 0x1FFFF


def _read_log(name: str) -> list[dict[str, Any]]:
    path = LOGS_DIR / f"{name}.jsonl"
    if not path.is_file():
        raise ToolError(f"no such log: {name!r}")
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _series(
    frames: list[dict[str, Any]], msg: codec.Message, signal: str
) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    for f in frames:
        if int(f["can_id"]) != msg.can_id:
            continue
        data = bytes.fromhex(str(f["data"]))
        if len(data) != msg.dlc:
            continue
        out.append((int(f["t_ms"]), codec.decode(msg, data)[signal]))
    return out


def decode_frame(can_id: int, data: str) -> str:
    """Decode one CAN/ISOBUS frame to physical signal values."""
    try:
        payload = bytes.fromhex(data)
    except ValueError as exc:
        raise ToolError(f"data is not valid hex: {exc}") from exc
    pgn = can_id & 0x3FFFF
    if _is_proprietary_pgn(pgn):
        raise ToolError(f"out of scope: proprietary PGN 0x{pgn:X} (public-standard only)")
    msg = _DB.get(can_id)
    if msg is None:
        raise ToolError(f"unknown can_id {can_id} (PGN 0x{pgn:X} not in the public catalog)")
    if len(payload) != msg.dlc:
        raise ToolError(f"bad DLC: {msg.name} expects {msg.dlc} bytes, got {len(payload)}")
    decoded = codec.decode(msg, payload)
    return json.dumps({"message": msg.name, "pgn": msg.pgn, "signals": decoded}, sort_keys=True)


def query_signal(log: str, signal: str) -> str:
    """Return the time series (t_ms, value) of a signal across a named bus log."""
    if signal not in _SIGNAL_INDEX:
        raise ToolError(f"unknown signal: {signal!r}")
    msg, _ = _SIGNAL_INDEX[signal]
    series = _series(_read_log(log), msg, signal)
    if not series:
        raise ToolError(f"signal {signal!r} not present in log {log!r}")
    return json.dumps({"signal": signal, "samples": series}, sort_keys=True)


def _classify(msg: codec.Message, sig: codec.Signal, series: list[tuple[int, float]]) -> str | None:
    values = [v for _, v in series]
    if sig.safety_bound is not None:
        lo, hi = sig.safety_bound
        if any(v < lo or v > hi for v in values):
            return "out_of_range"
    if msg.period_ms:
        span = series[-1][0] - series[0][0]
        expected = span // msg.period_ms + 1
        if len(series) < expected:
            return "dropout"
    if len(values) >= STUCK_MIN_SAMPLES and len(set(values)) == 1:
        return "stuck"
    if len(values) >= DRIFT_MIN_SAMPLES:
        deltas = [b - a for a, b in itertools.pairwise(values)]
        monotonic = all(d > 0 for d in deltas) or all(d < 0 for d in deltas)
        if monotonic and abs(values[-1] - values[0]) >= DRIFT_DELTA:
            return "drift"
    return None


def fault_check(log: str, signal: str = "") -> str:
    """Detect faults (out_of_range, dropout, stuck, drift) over a bus log.

    Evaluates monitored signals: those with a published safety bound, plus the
    periodic heartbeat (for dropout). Returns the detected faults, one per signal.
    """
    frames = _read_log(log)
    present = {int(f["can_id"]) for f in frames}
    faults: list[dict[str, str]] = []
    for msg in _DB.values():
        if msg.can_id not in present:
            continue
        monitored = [s for s in msg.signals if s.safety_bound is not None or msg.period_ms]
        for sig in monitored:
            if signal and sig.name != signal:
                continue
            series = _series(frames, msg, sig.name)
            if len(series) < 2:
                continue
            fault = _classify(msg, sig, series)
            if fault:
                faults.append({"signal": sig.name, "fault": fault})
    faults.sort(key=lambda d: d["signal"])
    return json.dumps({"log": log, "faults": faults}, sort_keys=True)


def safety_bound_check(signal: str, value: float) -> str:
    """Deterministic HARD gate: is `value` within the signal's safety bound?"""
    if signal not in _SIGNAL_INDEX:
        raise ToolError(f"unknown signal: {signal!r}")
    _, sig = _SIGNAL_INDEX[signal]
    if sig.safety_bound is None:
        raise ToolError(f"no safety bound defined for {signal!r}")
    lo, hi = sig.safety_bound
    unit = sig.unit or ""
    if lo <= value <= hi:
        return f"WITHIN: {value} {unit} in [{lo}, {hi}]".strip()
    return f"VIOLATION: {value} {unit} outside [{lo}, {hi}]".strip()


def sensor_fuse(log: str) -> str:
    """Cross-check wheel-based speed (km/h) against machine-selected speed (m/s)."""
    frames = _read_log(log)
    wheel_msg, _ = _SIGNAL_INDEX["WheelBasedVehicleSpeed"]
    mss_msg, _ = _SIGNAL_INDEX["MachineSelectedSpeed"]
    wheel = _series(frames, wheel_msg, "WheelBasedVehicleSpeed")
    mss = _series(frames, mss_msg, "MachineSelectedSpeed")
    if not wheel or not mss:
        raise ToolError(f"log {log!r} lacks both speed signals for fusion")
    wheel_kmh = wheel[-1][1]
    mss_kmh = round(mss[-1][1] * 3.6, 3)
    delta = round(abs(wheel_kmh - mss_kmh), 3)
    return json.dumps(
        {
            "wheel_kmh": wheel_kmh,
            "mss_kmh": mss_kmh,
            "delta_kmh": delta,
            "consistent": delta <= FUSION_TOL_KMH,
        },
        sort_keys=True,
    )


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "decode_frame",
        "description": (
            "Decode one CAN/ISOBUS frame to physical signal values using the public "
            "DBC. Pass the numeric can_id and the 8-byte payload as a hex string. "
            "Errors on proprietary (out-of-scope) PGNs, unknown ids, and bad DLC."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "can_id": {"type": "integer", "description": "frame id, e.g. 2147545092"},
                "data": {"type": "string", "description": "8-byte payload as hex"},
            },
            "required": ["can_id", "data"],
            "additionalProperties": False,
        },
    },
    {
        "name": "query_signal",
        "description": (
            "Return the time series (t_ms, value) of one signal across a named bus "
            "log (e.g. 'nominal', 'faults'). Call this to inspect how a signal behaves."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "log": {"type": "string", "description": "log name, e.g. nominal"},
                "signal": {"type": "string", "description": "signal name, e.g. EngineSpeed"},
            },
            "required": ["log", "signal"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fault_check",
        "description": (
            "Scan a bus log for faults (out_of_range, dropout, stuck, drift) across "
            "monitored signals. Optionally restrict to one signal. Returns the faults found."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "log": {"type": "string", "description": "log name, e.g. faults"},
                "signal": {"type": "string", "description": "optional: restrict to one signal"},
            },
            "required": ["log", "signal"],
            "additionalProperties": False,
        },
    },
    {
        "name": "safety_bound_check",
        "description": (
            "Deterministic safety gate: report WITHIN or VIOLATION for a signal value "
            "against its published operational bound. Call this before trusting or "
            "emitting any actuation value."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "signal": {"type": "string", "description": "signal name, e.g. CurvatureCommand"},
                "value": {"type": "number", "description": "the physical value to check"},
            },
            "required": ["signal", "value"],
            "additionalProperties": False,
        },
    },
    {
        "name": "sensor_fuse",
        "description": (
            "Cross-check wheel-based vehicle speed against machine-selected speed in a "
            "log; returns both in km/h, their delta, and whether they are consistent."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"log": {"type": "string", "description": "log name"}},
            "required": ["log"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Run a tool; returns (content, is_error)."""
    try:
        if name == "decode_frame":
            return decode_frame(int(tool_input["can_id"]), str(tool_input["data"])), False
        if name == "query_signal":
            return query_signal(str(tool_input["log"]), str(tool_input["signal"])), False
        if name == "fault_check":
            return fault_check(str(tool_input["log"]), str(tool_input.get("signal", ""))), False
        if name == "safety_bound_check":
            return safety_bound_check(str(tool_input["signal"]), float(tool_input["value"])), False
        if name == "sensor_fuse":
            return sensor_fuse(str(tool_input["log"])), False
        return f"unknown tool: {name}", True
    except (ToolError, TypeError, KeyError, ValueError) as exc:
        return f"tool error: {exc}", True
