"""
config.py — Central settings for the AI Ticket Triage Harness.

Keeping all tuneable values here means a reviewer (or auditor) can see
every threshold in one place without reading through the full codebase.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── AI model settings ────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Claude Haiku: fastest and cheapest model — good fit for classification tasks
# that don't need deep reasoning. Swap to claude-sonnet-4-5 if you need
# better accuracy on ambiguous tickets.
MODEL_ID    = "claude-haiku-4-5"
MAX_TOKENS  = 600

# ── Governance thresholds ────────────────────────────────────────────────────
# If the AI's confidence falls below this value, the ticket is routed to a
# human reviewer instead of being acted on automatically.
# Rationale: in a healthcare/aerospace context, low-confidence AI decisions
# should not be executed without human review. (NIST AI RMF — MS-2.5)
CONFIDENCE_THRESHOLD = 0.70

# ── File paths ───────────────────────────────────────────────────────────────
TICKETS_PATH   = "tickets/synthetic_tickets.json"
AUDIT_LOG_PATH = "audit_log.jsonl"

# ── Action definitions ───────────────────────────────────────────────────────
# Every possible action the system can take. Keeping them as constants means
# the audit log uses consistent, searchable labels.
ACTION_ESCALATE_IMMEDIATE   = "ESCALATE_HUMAN_IMMEDIATE"
ACTION_ESCALATE_HIPAA       = "ESCALATE_HIPAA_REVIEW"
ACTION_ESCALATE_SECURITY    = "ESCALATE_SECURITY_REVIEW"
ACTION_ESCALATE_LOW_CONF    = "ESCALATE_LOW_CONFIDENCE"
ACTION_AUTO_SUGGEST         = "AUTO_SUGGEST_FIX"
ACTION_ROUTE_TIER2          = "ROUTE_TIER2_SUPPORT"
