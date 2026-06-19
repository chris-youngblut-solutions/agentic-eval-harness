"""The data_semantic domain: NL->metric/SQL accuracy + metric-correctness over a
synthetic semantic layer.

The system under test is a data/analytics agent that, given a natural-language
question, maps it to the right governed metric, computes the metric's value (or
renders its canonical SQL) from the semantic layer rather than ad-hoc querying,
diagnoses a metric mismatch to a root cause, and never returns a numeric answer
that disagrees with the semantic layer's own definition — the analytics analogue
of a retrieval agent.

Everything is FABRICATED and GENERIC: the semantic model (metrics over a tiny
star schema), the fact rows, the NL questions, and the mismatch cases are all
synthetic, authored only to exercise the eval metrics. No real company data
model, metric catalog, BI semantic layer, or data is represented. See
fixtures/data_semantic/PROVENANCE.md.
"""

from __future__ import annotations

from agentic_eval.domain import Domain
from agentic_eval.domains.data_semantic import tools

SYSTEM_PROMPT = (
    "You are a data-analytics agent working a synthetic semantic layer (a catalog of "
    "governed metrics over a small fact table). Workflow: map the question to a metric "
    "with nl_to_metric (do not guess a metric id), look the metric up if you need its "
    "definition, then compute its value with metric_rollup or render its SQL with "
    "sql_for_metric — always go through the semantic layer rather than inventing an "
    "aggregation. Use consistency_check before finalizing any numeric answer: never "
    "report a value that disagrees with the metric's own computed value. "
    "When you have the answer, call submit_answer exactly once with the bare answer "
    "value (a number, a metric id, a SQL string, or a comma-separated list — no "
    "explanation)."
)

DOMAIN = Domain(
    name="data_semantic",
    system_prompt=SYSTEM_PROMPT,
    tool_schemas=tools.TOOL_SCHEMAS,
    execute_tool=tools.execute_tool,
)
