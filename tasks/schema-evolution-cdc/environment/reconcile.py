"""Legacy checkpoint maintenance from the pre-reconcile rollout."""

from __future__ import annotations


def advance_checkpoint(state: dict) -> dict:
    state["checkpoint"] = state["head"]
    return state
