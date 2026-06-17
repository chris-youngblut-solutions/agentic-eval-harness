# Industrial fixtures — provenance & data posture

This directory is the `industrial` domain's entire world: a curated public-standard
signal subset plus a synthetic bus corpus. It carries no proprietary, client, operator,
or machine-specific data.

## What is here

- `signals.json` — a curated subset of CAN/ISOBUS message + signal definitions.
- `logs/*.jsonl` — synthetic bus logs (`nominal`, `faults`, `fusion_mismatch`,
  `adversarial`), generated deterministically by
  `src/agentic_eval/domains/industrial/generate.py`.

## Decode ground-truth — source & license

The signal definitions in `signals.json` (bit layout, scale, offset, range, unit) are
copied from the public, MIT-licensed **opendbc-ag** repository at commit
**`a6d720972b38`** (`opendbc_ag/dbc/{j1939_ag_subset,iso11783_from_agisostack}.dbc`),
which in turn sources them from public references: the SAE J1939 PGN list on Wikipedia
and AgIsoStack++ (MIT). Bit layout, scale, offset, and range are copied as-is; unit
strings are normalized to ASCII (e.g. `degC` for the source's degree-Celsius glyph).

This is **public-standard only**. It contains:

- **No** proprietary or OEM-specific message definitions. The proprietary PGN ranges
  (SAE J1939 Proprietary A `0xEF00` and Proprietary B `0xFF00–0xFFFF`, and their
  extended-range equivalents) are deliberately excluded, and `decode_frame` rejects them
  at runtime as out of scope — mirroring opendbc-ag's CI scope policy.
- **No** machine serial numbers, ECU identifiers, VINs, or firmware versions.
- **No** operator, farm, field, or location identifiers.

## Synthetic corpus

The bus logs are entirely synthetic, produced by encoding known physical values through
the same public-standard codec. No log is a capture from any real vehicle or implement.
The injected faults (drift, out-of-range, stuck, dropout), the fusion mismatch, and the
adversarial frames (unknown id, proprietary PGN, short DLC) are authored for evaluation.

## Safety bounds are illustrative

The per-signal `safety_bound` values in `signals.json` are **illustrative operational
limits authored for this evaluation** to exercise the safety-bound metric. They are not
specifications, calibration values, or limits for any real machine, and must not be
relied on as such.

## No field-source leakage

This pack was authored from public standards and synthetic data only. It does not
incorporate any content from private diagnostic or field material (e.g. equipment
serial numbers, calibration constants, or operator context). Field methodology that
informs the domain framing is referenced only in its abstract, non-identifying form.
