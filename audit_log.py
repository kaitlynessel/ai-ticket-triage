"""
audit_log.py — Append-only audit log for the ticket triage harness.

Every ticket decision is recorded here: what the AI said, which rules fired,
what action was taken, and why. This is the proof that the system is operating
as designed — the most important piece for audits, compliance reviews, and
explaining AI decisions to stakeholders.

Format: JSONL (JSON Lines) — one JSON object per line, one line per ticket.
Why JSONL? Each line is independently parseable. Easy to tail, grep, or import
into a spreadsheet or SIEM tool. No need to load the entire file to read it.

This connects to:
  - NIST AI RMF (Govern 1.7): "AI risk management outcomes are documented."
  - HIPAA Security Rule: audit controls required for systems accessing ePHI.
  - AI governance principle of auditability: every automated decision must
    be explainable and traceable to a specific rule or model output.
"""

import json
import os
from datetime import datetime, timezone
from config import AUDIT_LOG_PATH


def write_entry(
    ticket: dict,
    agent_output: dict,
    harness_output: dict,
) -> dict:
    """
    Build and append one audit log entry.

    Returns the entry dict (useful for display / testing).
    """
    entry = {
        # When
        "timestamp": datetime.now(timezone.utc).isoformat(),

        # Who and what
        "ticket_id":    ticket.get("ticket_id"),
        "user_name":    ticket.get("user_name"),
        "user_role":    ticket.get("user_role"),
        "department":   ticket.get("department"),
        "subject":      ticket.get("subject"),

        # What the AI said
        "agent": {
            "mode":             agent_output.get("mode", "unknown"),
            "urgency":          agent_output.get("urgency"),
            "category":         agent_output.get("category"),
            "confidence":       agent_output.get("confidence"),
            "phi_detected":     agent_output.get("phi_detected", False),
            "security_concern": agent_output.get("security_concern", False),
            "suggested_fix":    agent_output.get("suggested_fix"),
            "reasoning":        agent_output.get("reasoning"),
        },

        # What the harness decided
        "harness": {
            "rules_fired":        harness_output.get("rules_fired", []),
            "final_action":       harness_output.get("final_action"),
            "escalation_reasons": harness_output.get("escalation_reasons", []),
            "overridden":         harness_output.get("overridden", False),
        },
    }

    # Append to the JSONL file (creates it if it doesn't exist)
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def read_all() -> list:
    """Read every entry from the audit log. Returns a list of dicts."""
    if not os.path.exists(AUDIT_LOG_PATH):
        return []
    with open(AUDIT_LOG_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def clear_log() -> None:
    """Delete the audit log (useful for resetting between demo runs)."""
    if os.path.exists(AUDIT_LOG_PATH):
        os.remove(AUDIT_LOG_PATH)
