"""Deterministic synthetic-corpus generator for the industrial domain.

Every nominal/fault frame is produced by `codec.encode`-ing known physical values,
so the expected decode is known by construction. There is no randomness: re-running
reproduces byte-identical logs (a test guards this). Run as a module to (re)write
the committed fixtures:

    uv run python -m agentic_eval.domains.industrial.generate

Logs (fixtures/industrial/logs/<name>.jsonl), each line `{"t_ms","can_id","data"}`:
- nominal           every signal varies slightly tick-to-tick (sensor noise), in
                    safety bounds, heartbeat increments every tick -> zero faults.
- faults            four distinct injected faults, one per signal:
                      EngineCoolantTemp        drift        (strictly rising, in-bound)
                      EngineSpeed              out_of_range (above the safety bound)
                      WheelBasedVehicleSpeed   stuck        (bit-identical every tick)
                      HeartbeatSequenceCounter dropout      (periodic frames missing)
- fusion_mismatch   wheel speed vs machine-selected speed disagree.
- adversarial       malformed frames: unknown id, proprietary-range PGN, short DLC.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_eval.domains.industrial import codec

LOGS_DIR = codec.SIGNALS_PATH.parent / "logs"
PROPRIETARY_CAN_ID = 0x80000000 | 0xEF00  # SAE J1939 Proprietary A range -> out of scope
UNKNOWN_CAN_ID = 0x80000000 | 0xDEAD  # not in the signal DB

EEC1, ET1, CCVS1, MSS, HEARTBEAT = (
    2147545092,
    2147548910,
    2147548913,
    2147545122,
    2147545316,
)


def _frame(
    db: dict[int, codec.Message], t_ms: int, can_id: int, values: dict[str, float]
) -> dict[str, Any]:
    data = codec.encode(db[can_id], values)
    return {"t_ms": t_ms, "can_id": can_id, "data": data.hex()}


def _nominal(db: dict[int, codec.Message]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    speeds = [1500, 1520, 1490, 1510, 1495, 1505]  # oscillates, not monotonic
    coolant = [85, 86, 85, 86, 85, 86]
    oil = [95, 96, 95, 96, 95, 96]  # every monitored signal must vary, else "stuck"
    wheel = [11.9, 12.0, 12.1, 12.0, 11.9, 12.0]  # noisy, not constant
    for i, t in enumerate(range(0, 600, 100)):
        frames.append(_frame(db, t, EEC1, {"EngineSpeed": speeds[i], "ActualEngineTorquePct": 40}))
        frames.append(
            _frame(db, t, ET1, {"EngineCoolantTemp": coolant[i], "EngineOilTemp1": oil[i]})
        )
        frames.append(_frame(db, t, CCVS1, {"WheelBasedVehicleSpeed": wheel[i]}))
        frames.append(_frame(db, t, MSS, {"MachineSelectedSpeed": wheel[i] / 3.6}))
        frames.append(_frame(db, t, HEARTBEAT, {"HeartbeatSequenceCounter": i}))
    return frames


def _faults(db: dict[int, codec.Message]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    coolant = [95, 98, 101, 104, 107, 110]  # strictly rising, in-bound -> drift
    speeds = [2995, 3005, 3000, 3010, 2998, 3002]  # all > 2700 safety -> out_of_range
    oil = [99, 100, 101, 100, 99, 100]  # varies -> not falsely flagged
    for i, t in enumerate(range(0, 600, 100)):
        frames.append(_frame(db, t, EEC1, {"EngineSpeed": speeds[i], "ActualEngineTorquePct": 55}))
        frames.append(
            _frame(db, t, ET1, {"EngineCoolantTemp": coolant[i], "EngineOilTemp1": oil[i]})
        )
        frames.append(_frame(db, t, CCVS1, {"WheelBasedVehicleSpeed": 12.0}))  # stuck
    # heartbeat present only at t=0 and t=500 -> dropout across the 600 ms window
    frames.append(_frame(db, 0, HEARTBEAT, {"HeartbeatSequenceCounter": 0}))
    frames.append(_frame(db, 500, HEARTBEAT, {"HeartbeatSequenceCounter": 5}))
    return sorted(frames, key=lambda f: (f["t_ms"], f["can_id"]))


def _fusion_mismatch(db: dict[int, codec.Message]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for t in range(0, 300, 100):
        frames.append(_frame(db, t, CCVS1, {"WheelBasedVehicleSpeed": 12.0}))  # 12 km/h
        frames.append(_frame(db, t, MSS, {"MachineSelectedSpeed": 5.0}))  # 5 m/s = 18 km/h
    return frames


def _adversarial() -> list[dict[str, Any]]:
    return [
        {"t_ms": 0, "can_id": UNKNOWN_CAN_ID, "data": "0011223344556677"},
        {"t_ms": 100, "can_id": PROPRIETARY_CAN_ID, "data": "0000000000000000"},
        {"t_ms": 200, "can_id": EEC1, "data": "00112233"},  # short DLC (4 bytes)
    ]


def build_corpus() -> dict[str, list[dict[str, Any]]]:
    db = load_db_strict()
    return {
        "nominal": _nominal(db),
        "faults": _faults(db),
        "fusion_mismatch": _fusion_mismatch(db),
        "adversarial": _adversarial(),
    }


def load_db_strict() -> dict[int, codec.Message]:
    return codec.load_db()


def write_corpus(out_dir: Path = LOGS_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frames in build_corpus().items():
        path = out_dir / f"{name}.jsonl"
        path.write_text("".join(json.dumps(f, sort_keys=True) + "\n" for f in frames))


if __name__ == "__main__":
    write_corpus()
    print(f"wrote corpus to {LOGS_DIR}")
