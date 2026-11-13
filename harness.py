"""
harness.py — Orchestrates the full triage pipeline for one ticket.

This is the "wrapper" around the agent. It:
  1. Calls the agent to classify the ticket.
  2. Passes the result through the governance rules.
  3. Writes the full decision to the audit log.
  4. Returns a human-readable result.

Keeping this separate from main.py means you can import and test
the harness in isolation, or swap in a different agent without
changing the governance layer.
"""

from agent     import classify
from rules     import apply_rules
from audit_log import write_entry


def process_ticket(ticket: dict, verbose: bool = False) -> dict:
    """
    Run one ticket through the full pipeline.

    Returns a result dict containing the ticket, agent output,
    harness output, and audit entry.
    """
    if verbose:
        print(f"\n{'─'*60}")
        print(f"  Ticket: {ticket['ticket_id']} | {ticket['subject'][:55]}")
        print(f"  User:   {ticket['user_name']} ({ticket['user_role']})")

    # Step 1 — Agent classifies the ticket
    agent_output = classify(ticket)

    if verbose:
        mode_label = "(LLM)" if agent_output.get("mode") == "llm" else "(keyword)"
        print(f"  Agent {mode_label}: urgency={agent_output['urgency']}, "
              f"category={agent_output['category']}, "
              f"confidence={agent_output['confidence']:.0%}")

    # Step 2 — Harness applies governance rules
    harness_output = apply_rules(ticket, agent_output)

    if verbose:
        if harness_output["rules_fired"]:
            print(f"  Rules fired: {', '.join(harness_output['rules_fired'])}")
        else:
            print(f"  Rules fired: none (agent decision stands)")
        print(f"  → Final action: {harness_output['final_action']}")

    # Step 3 — Write to audit log
    audit_entry = write_entry(ticket, agent_output, harness_output)

    return {
        "ticket":         ticket,
        "agent_output":   agent_output,
        "harness_output": harness_output,
        "audit_entry":    audit_entry,
    }


def process_batch(tickets: list, verbose: bool = True) -> list:
    """Process a list of tickets. Returns all results."""
    results = []
    for ticket in tickets:
        result = process_ticket(ticket, verbose=verbose)
        results.append(result)
    return results
