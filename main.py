"""
main.py — Demo runner for the AI Ticket Triage Harness.

Usage:
    python3 main.py

What it does:
  - Loads all synthetic tickets from tickets/synthetic_tickets.json
  - Runs each one through the agent + harness pipeline
  - Prints a summary table to the terminal
  - Saves a full audit log to audit_log.jsonl

Add your ANTHROPIC_API_KEY to .env to enable LLM classification.
Without it, the system uses keyword-based classification (still fully functional).
"""

import json
import sys
from config import TICKETS_PATH, ANTHROPIC_API_KEY
from harness import process_batch
from audit_log import clear_log, read_all

# Colour codes for terminal output (gracefully disabled on Windows)
try:
    import colorama; colorama.init()
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
except ImportError:
    RED = YELLOW = GREEN = CYAN = BOLD = RESET = ""

ACTION_COLORS = {
    "ESCALATE_HUMAN_IMMEDIATE":  RED,
    "ESCALATE_HIPAA_REVIEW":     YELLOW,
    "ESCALATE_SECURITY_REVIEW":  RED,
    "ESCALATE_LOW_CONFIDENCE":   YELLOW,
    "AUTO_SUGGEST_FIX":          GREEN,
    "ROUTE_TIER2_SUPPORT":       CYAN,
}


def _action_display(action: str) -> str:
    color = ACTION_COLORS.get(action, "")
    short = action.replace("_", " ").title()
    return f"{color}{short}{RESET}"


def print_summary(results: list) -> None:
    print(f"\n{'═'*90}")
    print(f"{BOLD}  TICKET TRIAGE SUMMARY{RESET}")
    print(f"{'═'*90}")

    # Header
    print(f"  {'ID':<10} {'URGENCY':<10} {'CATEGORY':<12} {'CONF':<7} {'FINAL ACTION':<35} {'RULES FIRED'}")
    print(f"  {'─'*10} {'─'*10} {'─'*12} {'─'*7} {'─'*35} {'─'*25}")

    for r in results:
        t   = r["ticket"]
        ao  = r["agent_output"]
        ho  = r["harness_output"]

        ticket_id   = t["ticket_id"]
        urgency     = ao.get("urgency", "?").upper()
        category    = ao.get("category", "?")
        conf        = f"{ao.get('confidence', 0):.0%}"
        action      = _action_display(ho["final_action"])
        rules       = ", ".join(r["rule"].replace("RULE_", "") for r in [
            {"rule": rn} for rn in ho["rules_fired"]
        ]) or "—"

        print(f"  {ticket_id:<10} {urgency:<10} {category:<12} {conf:<7} {action:<55} {rules}")

    print(f"{'═'*90}")


def print_escalation_details(results: list) -> None:
    """Print the full reasoning for any escalated ticket."""
    escalated = [r for r in results if r["harness_output"]["rules_fired"]]
    if not escalated:
        return

    print(f"\n{BOLD}  ESCALATION DETAILS{RESET}")
    print(f"{'─'*90}")
    for r in escalated:
        t   = r["ticket"]
        ho  = r["harness_output"]
        print(f"\n  {BOLD}{t['ticket_id']}{RESET} — {t['subject']}")
        print(f"  Submitted by: {t['user_name']} ({t['user_role']}, {t['department']})")
        for reason in ho["escalation_reasons"]:
            print(f"  ⚠  {reason}")


def print_stats(results: list) -> None:
    total      = len(results)
    escalated  = sum(1 for r in results if r["harness_output"]["rules_fired"])
    phi_flags  = sum(1 for r in results if r["agent_output"].get("phi_detected"))
    sec_flags  = sum(1 for r in results if r["agent_output"].get("security_concern"))
    overridden = sum(1 for r in results if r["harness_output"]["overridden"])

    print(f"\n{BOLD}  RUN STATISTICS{RESET}")
    print(f"  Total tickets processed : {total}")
    print(f"  Escalated by rules      : {escalated}  ({escalated/total:.0%})")
    print(f"  PHI flags raised        : {phi_flags}")
    print(f"  Security flags raised   : {sec_flags}")
    print(f"  Agent decisions overridden : {overridden}")
    mode = "LLM (Claude)" if ANTHROPIC_API_KEY else "Keyword (no API key)"
    print(f"  Classification mode     : {mode}")
    print(f"  Audit log written to    : audit_log.jsonl")


def main() -> None:
    print(f"\n{BOLD}2E WayFinder — AI Ticket Triage Harness{RESET}")
    print("Agent + Governance Harness Demo\n")

    # Load tickets
    try:
        with open(TICKETS_PATH, encoding="utf-8") as f:
            tickets = json.load(f)
        print(f"Loaded {len(tickets)} synthetic tickets from {TICKETS_PATH}")
    except FileNotFoundError:
        print(f"ERROR: Could not find {TICKETS_PATH}")
        sys.exit(1)

    # Clear previous run's audit log so each run is clean
    clear_log()
    print("Audit log cleared. Starting processing...\n")

    # Run all tickets through the pipeline
    results = process_batch(tickets, verbose=True)

    # Print summary table and details
    print_summary(results)
    print_escalation_details(results)
    print_stats(results)

    print(f"\n{'─'*90}")
    print("Done. Open audit_log.jsonl to review the full decision record.")
    print(f"{'─'*90}\n")


if __name__ == "__main__":
    main()
