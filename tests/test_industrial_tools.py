"""Industrial domain tools + codec + corpus generator — all keyless and deterministic."""

from __future__ import annotations

import json

import pytest

from agentic_eval.domains.industrial import codec, generate, tools

EEC1 = 2147545092
ET1 = 2147548910
PROPRIETARY = 0x80000000 | 0xEF00
UNKNOWN = 0x80000000 | 0xDEAD


def test_codec_roundtrip_is_exact_on_grid_values() -> None:
    db = codec.load_db()
    msg = db[EEC1]
    payload = codec.encode(msg, {"EngineSpeed": 1500.0, "ActualEngineTorquePct": 40.0})
    decoded = codec.decode(msg, payload)
    assert decoded["EngineSpeed"] == 1500.0
    assert decoded["ActualEngineTorquePct"] == 40.0


def test_decode_frame_reports_signals() -> None:
    out = json.loads(tools.decode_frame(EEC1, "0000a5e02e000000"))
    assert out["message"] == "J1939_EEC1_ElectronicEngineControl1"
    assert out["signals"]["EngineSpeed"] == 1500.0


def test_decode_frame_rejects_proprietary_pgn() -> None:
    content, is_error = tools.execute_tool(
        "decode_frame", {"can_id": PROPRIETARY, "data": "0000000000000000"}
    )
    assert is_error and "proprietary" in content


def test_decode_frame_rejects_bad_dlc_and_unknown() -> None:
    short, short_err = tools.execute_tool("decode_frame", {"can_id": EEC1, "data": "00112233"})
    assert short_err and "DLC" in short
    unk, unk_err = tools.execute_tool(
        "decode_frame", {"can_id": UNKNOWN, "data": "0011223344556677"}
    )
    assert unk_err and "unknown" in unk


def test_fault_check_nominal_is_clean() -> None:
    assert json.loads(tools.fault_check("nominal"))["faults"] == []


def test_fault_check_finds_the_four_injected_faults() -> None:
    faults = json.loads(tools.fault_check("faults"))["faults"]
    got = {f["signal"]: f["fault"] for f in faults}
    assert got == {
        "EngineCoolantTemp": "drift",
        "EngineSpeed": "out_of_range",
        "HeartbeatSequenceCounter": "dropout",
        "WheelBasedVehicleSpeed": "stuck",
    }


def test_fault_check_rejects_unknown_signal() -> None:
    # A bogus non-empty signal must fail loudly (like query_signal), not
    # silently return zero faults — the empty/omitted-signal scan-all path
    # is the only intended way to filter, so this guards against the
    # silent-empty trap that made an agent guess signal names.
    with pytest.raises(tools.ToolError):
        tools.fault_check("faults", "NotARealSignal")


def test_safety_bound_check_within_and_violation() -> None:
    assert tools.safety_bound_check("EngineSpeed", 1500).startswith("WITHIN")
    assert tools.safety_bound_check("EngineSpeed", 3010).startswith("VIOLATION")
    assert tools.safety_bound_check("CurvatureCommand", 5000).startswith("VIOLATION")


def test_safety_bound_check_errors_without_a_bound() -> None:
    with pytest.raises(tools.ToolError):
        tools.safety_bound_check("EngineTorqueMode", 1)


def test_sensor_fuse_consistent_then_mismatch() -> None:
    assert json.loads(tools.sensor_fuse("nominal"))["consistent"] is True
    assert json.loads(tools.sensor_fuse("fusion_mismatch"))["consistent"] is False


def test_corpus_generation_is_deterministic_and_matches_committed() -> None:
    built = generate.build_corpus()
    for name, frames in built.items():
        committed = [
            json.loads(line)
            for line in (generate.LOGS_DIR / f"{name}.jsonl").read_text().splitlines()
            if line
        ]
        assert frames == committed, f"committed {name}.jsonl is stale; regenerate"
