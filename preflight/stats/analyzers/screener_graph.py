"""Screener / skip-logic graph analysis (HP3 — static).

Builds a directed graph from the survey's conditional logic and screener
rules, then runs reachability and cycle detection. No LLM, no statistics —
this is a pure graph algorithms layer with low hallucination risk.

Detects:
  - dead_branch:        question depends on a prior conditional that can
                        never be true given the question's own type/options
  - loop:               cyclic conditional dependency (A → B → A)
  - self_loop:          a question conditioned on itself
  - unreachable_question: a question whose dependency comes after it in the
                        survey order
  - contradicting_rule: two screener rules that always disagree on the same
                        question/value
"""

from __future__ import annotations

from typing import Any

import networkx as nx

from preflight.logging import get_logger
from preflight.schemas.survey import Question, Survey
from preflight.stats.types import ScreenerFlag

logger = get_logger(__name__)


def _build_dependency_graph(survey: Survey) -> nx.DiGraph:
    g = nx.DiGraph()
    for q in survey.questions:
        g.add_node(q.id, type=q.type, position=survey.questions.index(q))
    for q in survey.questions:
        if q.conditional_on:
            g.add_edge(q.conditional_on.q_id, q.id, condition=q.conditional_on.model_dump())
    return g


def _detect_self_loops(graph: nx.DiGraph) -> list[ScreenerFlag]:
    flags: list[ScreenerFlag] = []
    for node in graph.nodes:
        if graph.has_edge(node, node):
            flags.append(
                ScreenerFlag(
                    type="self_loop",
                    description=f"question {node} is conditional on itself",
                    evidence={"question_id": node},
                    severity="high",
                    summary=(
                        f"Question {node} can never be reached because it's "
                        f"conditioned on its own answer. Remove the conditional."
                    ),
                )
            )
    return flags


def _detect_cycles(graph: nx.DiGraph) -> list[ScreenerFlag]:
    flags: list[ScreenerFlag] = []
    for cycle in nx.simple_cycles(graph):
        if len(cycle) <= 1:
            continue
        flags.append(
            ScreenerFlag(
                type="loop",
                description=f"cyclic conditional dependency: {' -> '.join(cycle)}",
                evidence={"cycle": cycle},
                severity="high",
                summary=(
                    f"Questions form a circular dependency ({' → '.join(cycle)}). "
                    f"None of them can be reached. Break the cycle."
                ),
            )
        )
    return flags


def _detect_forward_references(survey: Survey) -> list[ScreenerFlag]:
    pos = {q.id: i for i, q in enumerate(survey.questions)}
    flags: list[ScreenerFlag] = []
    for q in survey.questions:
        if not q.conditional_on:
            continue
        dep_id = q.conditional_on.q_id
        if dep_id not in pos:
            flags.append(
                ScreenerFlag(
                    type="dead_branch",
                    description=(
                        f"question {q.id} depends on unknown question {dep_id}"
                    ),
                    evidence={"question_id": q.id, "missing_dependency": dep_id},
                    severity="high",
                    summary=(
                        f"{q.id} won't appear to anyone — it's conditioned on "
                        f"{dep_id}, which doesn't exist in the survey."
                    ),
                )
            )
            continue
        if pos[dep_id] >= pos[q.id]:
            flags.append(
                ScreenerFlag(
                    type="unreachable_question",
                    description=(
                        f"question {q.id} (position {pos[q.id]}) depends on "
                        f"question {dep_id} (position {pos[dep_id]}) which is asked later"
                    ),
                    evidence={
                        "question_id": q.id,
                        "depends_on": dep_id,
                        "question_position": pos[q.id],
                        "dependency_position": pos[dep_id],
                    },
                    severity="high",
                    summary=(
                        f"{q.id} can never be answered: it depends on {dep_id}, "
                        f"which is asked later in the survey. Reorder or remove "
                        f"the conditional."
                    ),
                )
            )
    return flags


def _value_compatible_with_question(question: Question, value: Any) -> bool:
    """Check whether a conditional value could ever be matched by a response."""
    if question.type in ("likert_5", "top_box"):
        return isinstance(value, int) and 1 <= value <= 5
    if question.type == "likert_7":
        return isinstance(value, int) and 1 <= value <= 7
    if question.type == "nps":
        return isinstance(value, int) and 0 <= value <= 10
    if question.type == "single_choice":
        if not isinstance(value, int) or not question.options:
            return False
        return 0 <= value < len(question.options)
    if question.type == "multi_choice":
        if not isinstance(value, list) or not question.options:
            return False
        return all(isinstance(v, int) and 0 <= v < len(question.options) for v in value)
    return True


def _detect_impossible_conditionals(survey: Survey) -> list[ScreenerFlag]:
    by_id = {q.id: q for q in survey.questions}
    flags: list[ScreenerFlag] = []
    for q in survey.questions:
        if not q.conditional_on:
            continue
        dep = by_id.get(q.conditional_on.q_id)
        if dep is None:
            continue
        op = q.conditional_on.operator
        value = q.conditional_on.value
        if op in ("==", "!=", ">", ">=", "<", "<="):
            if not _value_compatible_with_question(dep, value):
                flags.append(
                    ScreenerFlag(
                        type="dead_branch",
                        description=(
                            f"question {q.id} requires {dep.id} {op} {value!r} which is "
                            f"incompatible with {dep.id}'s type ({dep.type})"
                        ),
                        evidence={
                            "question_id": q.id,
                            "depends_on": dep.id,
                            "operator": op,
                            "value": value,
                        },
                        severity="high",
                        summary=(
                            f"{q.id} can never be reached because no valid response "
                            f"to {dep.id} can satisfy the condition ({op} {value!r})."
                        ),
                    )
                )
    return flags


def _detect_contradicting_screener_rules(survey: Survey) -> list[ScreenerFlag]:
    by_question: dict[str, list[tuple[int, Any]]] = {}
    for idx, rule in enumerate(survey.screener.rules):
        by_question.setdefault(rule.q_id, []).append((idx, rule))

    flags: list[ScreenerFlag] = []
    for q_id, rules in by_question.items():
        terminates = [r for _, r in rules if r.action == "terminate"]
        qualifies = [r for _, r in rules if r.action == "qualify"]
        for t_rule in terminates:
            for q_rule in qualifies:
                if t_rule.if_value_in is None or q_rule.if_value_in is None:
                    continue
                overlap = set(t_rule.if_value_in) & set(q_rule.if_value_in)
                if overlap:
                    flags.append(
                        ScreenerFlag(
                            type="contradicting_rule",
                            description=(
                                f"screener on {q_id} both terminates and qualifies on "
                                f"value(s) {sorted(overlap)}"
                            ),
                            summary=(
                                f"Screener rule conflict on {q_id}: value(s) "
                                f"{sorted(overlap)} are both terminated and qualified. "
                                f"Pick one action per value."
                            ),
                            evidence={
                                "question_id": q_id,
                                "overlapping_values": sorted(overlap),
                            },
                            severity="high",
                        )
                    )
    return flags


def analyze(survey: Survey) -> list[ScreenerFlag]:
    graph = _build_dependency_graph(survey)
    flags: list[ScreenerFlag] = []
    flags.extend(_detect_self_loops(graph))
    flags.extend(_detect_cycles(graph))
    flags.extend(_detect_forward_references(survey))
    flags.extend(_detect_impossible_conditionals(survey))
    flags.extend(_detect_contradicting_screener_rules(survey))
    logger.info("screener.complete", n_questions=len(survey.questions), n_flags=len(flags))
    return flags
