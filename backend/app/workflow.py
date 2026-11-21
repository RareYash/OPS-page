"""
Workflow state machine — the single place where transitions are decided.

States: open → in_progress → pending_approval → resolved → closed
Plus: resolved → open (reopen)

Anything not in the transition table is rejected with 409.
"""

from app.models import Role


# ---------------------------------------------------------------------------
# Transition table
# Each key is (from_status, to_status) → requirements dict
# ---------------------------------------------------------------------------

TRANSITIONS: dict[tuple[str, str], dict] = {
    ("open", "in_progress"): {
        "min_role": Role.member,
        "must_be_assignee": True,
        "needs_assignee": True,
        "label": "Start work",
    },
    ("in_progress", "resolved"): {
        "min_role": Role.member,
        "must_be_assignee": True,
        "requires_approval_false": True,  # only if requires_approval is False
        "label": "Resolve",
    },
    ("in_progress", "pending_approval"): {
        "min_role": Role.member,
        "must_be_assignee": True,
        "requires_approval_true": True,  # only if requires_approval is True
        "label": "Submit for approval",
    },
    ("pending_approval", "resolved"): {
        "min_role": Role.lead,
        "must_not_be_assignee": True,  # separation of duties
        "label": "Approve",
    },
    ("pending_approval", "in_progress"): {
        "min_role": Role.lead,
        "must_not_be_assignee": True,
        "comment_required": True,  # rejection must include a comment
        "label": "Reject (send back)",
    },
    ("resolved", "closed"): {
        "min_role": Role.lead,
        "label": "Close",
    },
    ("resolved", "open"): {
        "min_role": Role.member,
        "label": "Reopen",
    },
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """Check if a transition exists in the state machine."""
    if hasattr(from_status, "value"):
        from_status = from_status.value
    return (from_status, to_status) in TRANSITIONS


def get_transition_requirements(from_status: str, to_status: str) -> dict | None:
    """Get the requirements for a transition, or None if invalid."""
    if hasattr(from_status, "value"):
        from_status = from_status.value
    return TRANSITIONS.get((from_status, to_status))


def check_transition(
    item, user, to_status: str, comment: str | None = None
) -> tuple[bool, str | None]:
    """
    Validate a transition for a given item and user.
    Returns (allowed, reason) — reason is None if allowed, a message if not.
    """
    from_status = item.status.value if hasattr(item.status, "value") else item.status

    reqs = get_transition_requirements(from_status, to_status)
    if reqs is None:
        return False, f"Transition from '{from_status}' to '{to_status}' is not allowed"

    # Check assignee requirements
    if reqs.get("needs_assignee") and item.assignee_id is None:
        return False, "Item must have an assignee before starting work"

    if reqs.get("must_be_assignee") and item.assignee_id != user.id:
        return False, "Only the assignee can perform this transition"

    if reqs.get("must_not_be_assignee") and item.assignee_id == user.id:
        return False, "You cannot approve or reject your own assigned item (separation of duties)"

    # Check approval-related rules
    if reqs.get("requires_approval_false") and item.requires_approval:
        return (
            False,
            "This item requires approval. Submit for approval instead of resolving directly",
        )

    if reqs.get("requires_approval_true") and not item.requires_approval:
        return (
            False,
            "This item does not require approval. Resolve it directly",
        )

    # Comment required for rejection
    if reqs.get("comment_required") and not comment:
        return False, "A comment is required when rejecting an item"

    return True, None
