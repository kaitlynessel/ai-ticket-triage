"""
agent.py — AI classification agent for the ticket triage harness.

The agent reads a ticket and returns a structured classification:
  - urgency:          critical / high / medium / low
  - category:         network / hardware / software / access / security / other
  - confidence:       0.0–1.0 (how certain the agent is)
  - suggested_action: what the agent recommends doing
  - suggested_fix:    plain-language troubleshooting suggestion
  - reasoning:        why the agent made this classification
  - phi_detected:     True if the agent flagged PHI-related content
  - security_concern: True if the agent flagged a security concern

The agent runs in one of two modes:
  - KEYWORD MODE (default): uses pattern matching. No API key required.
    Fast, free, deterministic. Good for demos and testing.
  - LLM MODE: uses Claude Haiku via the Anthropic API for richer reasoning.
    Activated automatically when ANTHROPIC_API_KEY is set in .env.

The harness in harness.py runs AFTER the agent and can override its output.
The agent's job is to classify; the harness decides what actually happens.
"""

import json
import re
from config import (
    ANTHROPIC_API_KEY, MODEL_ID, MAX_TOKENS,
    ACTION_AUTO_SUGGEST, ACTION_ROUTE_TIER2,
)
from rules import PHI_KEYWORDS, SECURITY_KEYWORDS, _text_contains_any


# ── Keyword classification (always available) ─────────────────────────────────

URGENCY_PATTERNS = {
    "critical": [
        r"ransomware", r"encrypt", r"bitcoin", r"critical",
        r"immediate(ly)?", r"patient\s+safety", r"crashed\s+mid",
    ],
    "high": [
        r"shift\s+in\s+\d+\s+minutes?", r"can.t\s+(access|connect|log\s+in)",
        r"urgent", r"right\s+now", r"immediately", r"ehr", r"medication",
        r"patient\s+assignment", r"badge\s+reader",
    ],
    "medium": [
        r"slow(er|ing)?", r"keeps?\s+crashing", r"not\s+work(ing)?",
        r"error", r"can.t\s+open", r"won.t\s+(start|boot|turn\s+on)",
        r"end.of.month", r"reporting",
    ],
}

CATEGORY_PATTERNS = {
    "security": [
        r"ransomware", r"phish(ing)?", r"breach", r"unauthorized",
        r"malware", r"suspicious\s+link", r"credentials?", r"bitcoin",
        r"encrypted\s+files?",
    ],
    "network": [
        r"vpn", r"wifi", r"wi-fi", r"internet", r"network", r"connect(ion)?",
        r"remote\s+access",
    ],
    "access": [
        r"password", r"login", r"log\s+in", r"log\s+out", r"badge",
        r"account", r"permission", r"access", r"locked\s+out",
        r"can.t\s+log", r"new\s+(employee|hire|user)",
    ],
    "hardware": [
        r"laptop", r"computer", r"screen", r"keyboard", r"mouse",
        r"won.t\s+(turn\s+on|boot|power)", r"battery", r"monitor",
        r"printer", r"badge\s+reader",
    ],
    "software": [
        r"app(lication)?", r"software", r"program", r"teams",
        r"excel", r"outlook", r"crash(ing|es)?", r"error\s+message",
        r"install", r"update", r"pacs", r"ehr\s+software", r"dosing",
    ],
}


def _keyword_classify(ticket: dict) -> dict:
    """
    Classify a ticket using keyword pattern matching.
    Returns a classification dict. Confidence reflects how many signals matched.
    """
    text = f"{ticket.get('subject', '')} {ticket.get('body', '')}".lower()

    # --- Urgency ---
    urgency = "low"
    urgency_signals = 0
    for level in ("critical", "high", "medium"):
        for pattern in URGENCY_PATTERNS.get(level, []):
            if re.search(pattern, text, re.IGNORECASE):
                urgency = level
                urgency_signals += 1
                break
        if urgency_signals:
            break

    # Also consider self-reported urgency
    self_urgency = ticket.get("self_reported_urgency", "").lower()
    if self_urgency in ("critical", "urgent", "high"):
        urgency = "critical" if self_urgency == "critical" else "high"
        urgency_signals += 1

    # --- Category ---
    category = "other"
    category_signals = 0
    for cat, patterns in CATEGORY_PATTERNS.items():
        matches = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
        if matches > category_signals:
            category_signals = matches
            category = cat

    # --- Special flags ---
    phi_detected      = _text_contains_any(text, PHI_KEYWORDS)
    security_concern  = _text_contains_any(text, SECURITY_KEYWORDS)

    if security_concern:
        category = "security"
        urgency  = "critical"

    # --- Confidence: based on signal strength ---
    total_signals = urgency_signals + category_signals
    if total_signals >= 5:
        confidence = 0.85
    elif total_signals >= 3:
        confidence = 0.75
    elif total_signals >= 2:
        confidence = 0.65
    else:
        confidence = 0.50   # Ambiguous ticket — below threshold → human review

    # --- Suggested action ---
    suggested_action = (
        ACTION_ROUTE_TIER2 if urgency in ("high", "critical")
        else ACTION_AUTO_SUGGEST
    )

    # --- Generate a plain-language fix suggestion ---
    fix_map = {
        "network":   "Check VPN client settings and restart the network adapter. If the issue persists, verify credentials and try a different network.",
        "hardware":  "Perform a hard reset (hold power 10 seconds). If the device still fails to respond, escalate to on-site hardware support.",
        "software":  "Close all instances of the application, clear the cache, and restart. If the issue persists, uninstall and reinstall.",
        "access":    "Submit an identity verification request to IT for account reset. For badge access, contact physical security.",
        "security":  "DO NOT interact with any files or notifications. Disconnect from the network immediately. Contact the security team.",
        "other":     "Additional information may be needed. A technician will follow up to gather details.",
    }
    suggested_fix = fix_map.get(category, fix_map["other"])

    return {
        "urgency":          urgency,
        "category":         category,
        "confidence":       round(confidence, 2),
        "suggested_action": suggested_action,
        "suggested_fix":    suggested_fix,
        "phi_detected":     phi_detected,
        "security_concern": security_concern,
        "reasoning":        f"Keyword classification. Urgency signals: {urgency_signals}, category signals: {category_signals}.",
        "mode":             "keyword",
    }


# ── LLM classification (requires ANTHROPIC_API_KEY in .env) ──────────────────

LLM_PROMPT = """You are an IT helpdesk triage agent. Classify this support ticket and return a JSON object only — no extra text.

TICKET:
Subject: {subject}
Body: {body}
User role: {user_role}
Self-reported urgency: {self_urgency}

Return ONLY this JSON structure:
{{
  "urgency": "critical|high|medium|low",
  "category": "network|hardware|software|access|security|other",
  "confidence": 0.0 to 1.0,
  "suggested_action": "AUTO_SUGGEST_FIX|ROUTE_TIER2_SUPPORT",
  "suggested_fix": "plain-language troubleshooting step (1-2 sentences)",
  "phi_detected": true or false,
  "security_concern": true or false,
  "reasoning": "1-2 sentence explanation of your classification"
}}

Rules for classification:
- urgency=critical: immediate threat to patient safety, ransomware, or complete clinical system outage
- urgency=high: clinical user blocked from patient care, or urgent self-reported
- phi_detected=true: any mention of patient data, PHI, HIPAA, EHR, medical records, diagnoses
- security_concern=true: ransomware, phishing, unauthorized access, suspicious links or emails
- confidence: how certain you are, 0.0-1.0"""


def _llm_classify(ticket: dict) -> dict:
    """Classify using Claude Haiku. Falls back to keyword mode on any error."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        prompt = LLM_PROMPT.format(
            subject     = ticket.get("subject", ""),
            body        = ticket.get("body", ""),
            user_role   = ticket.get("user_role", "unknown"),
            self_urgency= ticket.get("self_reported_urgency", "not specified"),
        )

        response = client.messages.create(
            model      = MODEL_ID,
            max_tokens = MAX_TOKENS,
            messages   = [{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        result = json.loads(raw)
        result["mode"] = "llm"
        return result

    except Exception as exc:
        print(f"  [agent] LLM classification failed ({exc}). Falling back to keyword mode.")
        fallback = _keyword_classify(ticket)
        fallback["mode"] = "keyword_fallback"
        return fallback


# ── Public entry point ────────────────────────────────────────────────────────

def classify(ticket: dict) -> dict:
    """
    Classify a single ticket. Uses LLM if API key is configured, otherwise keywords.
    Returns a classification dict that the harness will process.
    """
    if ANTHROPIC_API_KEY:
        return _llm_classify(ticket)
    return _keyword_classify(ticket)
