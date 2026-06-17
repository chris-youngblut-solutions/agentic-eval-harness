"""Deterministic CAN/ISOBUS bit-field codec over the public-standard signal subset
(fixtures/industrial/signals.json).

Intel/little-endian unsigned layout (DBC `@1+`): read the 8-byte payload as a
little-endian integer P, then for a signal at (start, length):

    raw      = (P >> start) & ((1 << length) - 1)
    physical = raw * scale + offset

`decode` and `encode` are exact inverses up to the signal's quantization step
(`scale`). That inverse property is what lets the synthetic corpus carry a
*computed* ground truth: every frame is produced by `encode`-ing known physical
values, so the expected decode is known by construction, not asserted by hand.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_eval.domain import ROOT

SIGNALS_PATH = ROOT / "fixtures" / "industrial" / "signals.json"
_PAYLOAD_BYTES = 8


@dataclass(frozen=True)
class Signal:
    name: str
    start: int
    length: int
    scale: float
    offset: float
    min: float
    max: float
    unit: str
    safety_bound: tuple[float, float] | None


@dataclass(frozen=True)
class Message:
    name: str
    pgn: int
    can_id: int
    bus: str
    dlc: int
    domain: str
    actuation: bool
    period_ms: int | None
    signals: list[Signal]

    def signal(self, name: str) -> Signal:
        for sig in self.signals:
            if sig.name == name:
                return sig
        raise KeyError(f"{self.name} has no signal {name!r}")


def _signal_from_raw(raw: dict[str, Any]) -> Signal:
    bound = raw.get("safety_bound")
    return Signal(
        name=str(raw["name"]),
        start=int(raw["start"]),
        length=int(raw["length"]),
        scale=float(raw["scale"]),
        offset=float(raw["offset"]),
        min=float(raw["min"]),
        max=float(raw["max"]),
        unit=str(raw["unit"]),
        safety_bound=(float(bound["min"]), float(bound["max"])) if bound else None,
    )


def _message_from_raw(raw: dict[str, Any]) -> Message:
    return Message(
        name=str(raw["name"]),
        pgn=int(raw["pgn"]),
        can_id=int(raw["can_id"]),
        bus=str(raw["bus"]),
        dlc=int(raw["dlc"]),
        domain=str(raw.get("domain", "ot")),
        actuation=bool(raw.get("actuation", False)),
        period_ms=int(raw["period_ms"]) if raw.get("period_ms") is not None else None,
        signals=[_signal_from_raw(s) for s in raw["signals"]],
    )


def load_db(path: Path = SIGNALS_PATH) -> dict[int, Message]:
    """Load the signal database, keyed by can_id."""
    raw: dict[str, Any] = json.loads(path.read_text())
    messages = [_message_from_raw(m) for m in raw["messages"]]
    return {m.can_id: m for m in messages}


def decode_signal(sig: Signal, payload: int) -> float:
    raw = (payload >> sig.start) & ((1 << sig.length) - 1)
    value = raw * sig.scale + sig.offset
    return round(value, 6)


def decode(msg: Message, data: bytes) -> dict[str, float]:
    """Decode every signal in a message from its 8-byte payload."""
    payload = int.from_bytes(data, "little")
    return {sig.name: decode_signal(sig, payload) for sig in msg.signals}


def encode(msg: Message, values: dict[str, float]) -> bytes:
    """Encode physical values into an 8-byte payload (inverse of decode).

    Each raw field is clamped to its bit width, so out-of-range physical inputs
    saturate rather than corrupting adjacent fields — useful for authoring
    fixtures that probe range/saturation behavior deterministically.
    """
    payload = 0
    for name, value in values.items():
        sig = msg.signal(name)
        raw = round((value - sig.offset) / sig.scale)
        raw = max(0, min(raw, (1 << sig.length) - 1))
        payload |= raw << sig.start
    return payload.to_bytes(_PAYLOAD_BYTES, "little")
