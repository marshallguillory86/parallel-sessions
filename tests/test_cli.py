"""Tests for parallel-sessions CLI."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from parallel_sessions.cli import build_parser, validate_plan


def _plan(*threads: dict) -> dict:
    return {"threads": list(threads)}


def _t(tid: int, **kw) -> dict:
    base = {
        "id": tid,
        "branch": kw.pop("branch", f"branch-{tid}"),
        "goal": kw.pop("goal", f"goal {tid}"),
        "owns": kw.pop("owns", [f"path-{tid}/"]),
    }
    base.update(kw)
    return base


# ---------- thread-count gate ------------------------------------------------


def test_accepts_three_clean_threads():
    threads = validate_plan(_plan(_t(1), _t(2), _t(3)))
    assert [t["id"] for t in threads] == [1, 2, 3]


def test_accepts_five_clean_threads():
    threads = validate_plan(_plan(_t(1), _t(2), _t(3), _t(4), _t(5)))
    assert len(threads) == 5


def test_rejects_two_threads():
    with pytest.raises(SystemExit):
        validate_plan(_plan(_t(1), _t(2)))


def test_rejects_six_threads():
    with pytest.raises(SystemExit):
        validate_plan(_plan(_t(1), _t(2), _t(3), _t(4), _t(5), _t(6)))


# ---------- required-fields gate --------------------------------------------


def test_rejects_missing_goal():
    bad = {"id": 1, "branch": "b1", "owns": ["a/"]}
    with pytest.raises(SystemExit):
        validate_plan(_plan(bad, _t(2), _t(3)))


def test_rejects_missing_owns():
    bad = {"id": 1, "branch": "b1", "goal": "g"}
    with pytest.raises(SystemExit):
        validate_plan(_plan(bad, _t(2), _t(3)))


# ---------- uniqueness gates -------------------------------------------------


def test_rejects_duplicate_ids():
    with pytest.raises(SystemExit):
        validate_plan(_plan(_t(1), _t(1, branch="b1b"), _t(3)))


def test_rejects_duplicate_branch_names():
    with pytest.raises(SystemExit):
        validate_plan(
            _plan(
                _t(1, branch="x"),
                _t(2, branch="x"),
                _t(3, branch="y"),
            )
        )


# ---------- path-overlap gate ------------------------------------------------


def test_rejects_identical_owned_paths():
    with pytest.raises(SystemExit):
        validate_plan(
            _plan(
                _t(1, owns=["services/auth/"]),
                _t(2, owns=["services/auth/"]),
                _t(3, owns=["services/payments/"]),
            )
        )


def test_rejects_prefix_overlap():
    with pytest.raises(SystemExit):
        validate_plan(
            _plan(
                _t(1, owns=["services/auth/"]),
                _t(2, owns=["services/auth/middleware/"]),
                _t(3, owns=["services/payments/"]),
            )
        )


def test_accepts_disjoint_sibling_paths():
    threads = validate_plan(
        _plan(
            _t(1, owns=["services/auth/"]),
            _t(2, owns=["services/payments/"]),
            _t(3, owns=["services/orders/"]),
        )
    )
    assert len(threads) == 3


def test_accepts_substring_but_not_prefix():
    # services/auth-v2 is NOT a child of services/auth — they're siblings.
    threads = validate_plan(
        _plan(
            _t(1, owns=["services/auth/"]),
            _t(2, owns=["services/auth-v2/"]),
            _t(3, owns=["services/payments/"]),
        )
    )
    assert len(threads) == 3


# ---------- example plan ----------------------------------------------------


def test_example_plan_is_valid():
    example = Path(__file__).resolve().parent.parent / "templates" / "plan.toml.example"
    with example.open("rb") as f:
        plan = tomllib.load(f)
    threads = validate_plan(plan)
    assert len(threads) >= 3


# ---------- argparse wiring -------------------------------------------------


def test_parser_has_all_subcommands():
    parser = build_parser()
    sub_actions = [a for a in parser._actions if a.dest == "cmd"]
    assert sub_actions, "expected a 'cmd' subparser action"
    choices = set(sub_actions[0].choices)
    assert {"fanout", "status", "converge", "cleanup"}.issubset(choices)
