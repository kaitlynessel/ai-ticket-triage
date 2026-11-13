"""
rules.py — Governance rules for the AI Ticket Triage Harness.

These rules run AFTER the AI agent and can OVERRIDE its decision.
They represent the policies an organization would set before deploying any AI
to handle real tickets. No AI output passes through without being checked here.

Design principle: rules are readable by non-engineers. A compliance officer,
auditor, or department head should be able to open this file and understand
every policy without needing to know Python.

Connection to AI governance frameworks:
  - NIST AI RMF (Govern 1.1): policies define what the AI is and isn't allowed to do.
  - NIST AI RMF (Measure 2.5): human oversight is required when AI confidence is low.
  - HIPAA Security Rule §164.308(a)(1): incidents involving ePHI require escalation and review.
  - Human-in-the-loop design: clinical safety and security incidents always require a human decision.
"""

from config import (
    CONFIDENCE_THRESHOLD,
    ACTION_ESCALATE_IMMEDIATE,
    ACTION_ESCALATE_HIPAA,
    ACTION_ESCALATE_SECURITY,
    ACTION_ESCALATE_LOW_CONF,
)

# ── Keywords that trigger specific rules ─────────────────────────────────────

CLINICAL_ROLES = {
    "nurse", "physician", "doctor", "clinician", "radiologist",
    "pharmacist", "nurse_practitioner", "pa", "technician_clinical",
    "radiologist",
}

PHI_KEYWORDS = {
    "patient data", "phi", "hipaa", "medical record", "health information",
    "ehr", "electronic health record", "patient name", "diagnosis",
    "protected health", "medical history", "patient file",
}

SECURITY_KEYWORDS = {
    "ransomware", "phishing", "breach", "unauthorized access", "malware",
    "suspicious link", "clicked a link", "bitcoin", "encrypted files",
    "credentials", "suspicious email", "hacked", "virus",
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _text_contains_any(text: str, keywords: set) -> bool:
    """Return True if the lowercased text contains any of the given keywords."""
    lowered = text.lower()
    return any(kw in lowered for kw in keywords)

def _ticket_text(ticket: dict) -> str:
    """Combine subject + body for keyword scanning."""
    return f"{ticket.get('subject', '')} {ticket.get('body', '')}"

def _is_clinical_user(ticket: dict) -> bool:
    """Return True if the ticket submitter is in a clinical role."""
    role = ticket.get("user_role", "").lower().replace(" ", "_")
    return role in CLINICAL_ROLES


# ── Rules ─────────────────────────────────────────────────────────────────────
# Each rule is a function that returns either None (rule does not apply)
# or a dict describing what should happen and why.

def rule_clinical_high_urgency(ticket: dict, agent_output: dict) -> dict:
    """
    RULE: Clinical user + high urgency → immediate human escalation.

    WHY IT EXISTS:
    Clinical staff (nurses, physicians, radiologists, pharmacists) work in
    environments where IT failures can directly affect patient safety.
    A nurse who can't access the EHR or a medication room poses an immediate
    clinical risk. This rule ensures those tickets are never auto-resolved
    or delayed — they always reach a human immediately.

    The AI is not allowed to auto-suggest a fix and close a ticket when a
    patient's care could be affected.
    """
    urgency = agent_output.get("urgency", "").lower()
    if _is_clinical_user(ticket) and urgency in ("high", "critical"):
        return {
            "rule": "RULE_CLINICAL_HIGH_URGENCY",
            "action": ACTION_ESCALATE_IMMEDIATE,
            "reason": (
                f"Clinical user ({ticket.get('user_role')}) with {urgency} urgency. "
                "Patient safety may be affected — requires immediate human response."
            ),
        }
    return None


def rule_phi_detected(ticket: dict, agent_output: dict) -> dict:
    """
    RULE: Any mention of PHI or patient data → escalate for HIPAA review.

    WHY IT EXISTS:
    HIPAA requires that any potential breach or unauthorized disclosure of
    Protected Health Information (ePHI) be escalated, investigated, and
    documented within specific timeframes. An AI agent cannot make that
    compliance determination — a human must review it.

    This rule catches both accidental disclosures (wrong email sent) and
    access requests involving patient records.
    """
    full_text = _ticket_text(ticket)
    phi_in_ticket = _text_contains_any(full_text, PHI_KEYWORDS)
    phi_flagged_by_agent = agent_output.get("phi_detected", False)

    if phi_in_ticket or phi_flagged_by_agent:
        return {
            "rule": "RULE_PHI_DETECTED",
            "action": ACTION_ESCALATE_HIPAA,
            "reason": (
                "Ticket contains references to patient data, PHI, or HIPAA-sensitive information. "
                "Requires HIPAA compliance review before any action is taken."
            ),
        }
    return None


def rule_security_incident(ticket: dict, agent_output: dict) -> dict:
    """
    RULE: Any security concern → escalate to security team immediately.

    WHY IT EXISTS:
    Security incidents (ransomware, phishing, credential theft) can spread
    rapidly across a network. An AI triage agent should never attempt to
    'resolve' a potential security incident — it must immediately alert the
    security team and potentially isolate affected systems.

    Speed matters here: a delayed response to ransomware can result in
    encrypted systems across an entire organization within minutes.
    """
    full_text = _ticket_text(ticket)
    security_in_ticket   = _text_contains_any(full_text, SECURITY_KEYWORDS)
    security_by_agent    = agent_output.get("security_concern", False)
    category_is_security = agent_output.get("category", "").lower() == "security"

    if security_in_ticket or security_by_agent or category_is_security:
        return {
            "rule": "RULE_SECURITY_INCIDENT",
            "action": ACTION_ESCALATE_SECURITY,
            "reason": (
                "Ticket contains indicators of a security incident (phishing, ransomware, breach, "
                "credential theft, or unauthorized access). Requires immediate security team response."
            ),
        }
    return None


def rule_low_confidence(ticket: dict, agent_output: dict) -> dict:
    """
    RULE: AI confidence below threshold → route to human reviewer.

    WHY IT EXISTS:
    When the AI is uncertain, acting on that uncertainty can cause more harm
    than simply routing the ticket to a human. This is the fundamental
    human-in-the-loop principle: AI handles what it's confident about;
    humans handle what it's not.

    The threshold is set in config.py and can be adjusted by policy.
    Current threshold: {threshold} (70%).
    """.format(threshold=CONFIDENCE_THRESHOLD)
    confidence = agent_output.get("confidence", 0.0)
    if confidence < CONFIDENCE_THRESHOLD:
        return {
            "rule": "RULE_LOW_CONFIDENCE",
            "action": ACTION_ESCALATE_LOW_CONF,
            "reason": (
                f"AI confidence ({confidence:.0%}) is below the required threshold "
                f"({CONFIDENCE_THRESHOLD:.0%}). Routing to human reviewer."
            ),
        }
    return None


def rule_no_auto_close_critical(ticket: dict, agent_output: dict) -> dict:
    """
    RULE: Tickets self-reported as 'critical' cannot be auto-closed.

    WHY IT EXISTS:
    When a user marks their own ticket as critical, that self-assessment carries
    weight regardless of what the AI thinks. The agent might classify the urgency
    differently, but a human must make the final call on any ticket the submitter
    themselves deemed critical.

    This prevents the AI from downgrading the perceived severity of a situation
    the user knows is serious — the user has context the AI doesn't have.
    """
    self_urgency = ticket.get("self_reported_urgency", "").lower()
    if self_urgency == "critical":
        return {
            "rule": "RULE_NO_AUTO_CLOSE_CRITICAL",
            "action": ACTION_ESCALATE_IMMEDIATE,
            "reason": (
                "User self-reported urgency as 'critical'. "
                "Human review required regardless of AI classification."
            ),
        }
    return None


# ── Rule runner ───────────────────────────────────────────────────────────────

ALL_RULES = [
    rule_clinical_high_urgency,
    rule_phi_detected,
    rule_security_incident,
    rule_low_confidence,
    rule_no_auto_close_critical,
]

# Priority order for escalation actions (higher index = higher priority).
# If multiple rules fire, the highest-priority action wins.
ACTION_PRIORITY = {
    ACTION_ESCALATE_HIPAA:     3,
    ACTION_ESCALATE_SECURITY:  4,   # Security incidents are the highest priority
    ACTION_ESCALATE_IMMEDIATE: 2,
    ACTION_ESCALATE_LOW_CONF:  1,
}


def apply_rules(ticket: dict, agent_output: dict) -> dict:
    """
    Run all governance rules against a ticket and agent output.

    Returns a dict with:
      - rules_fired: list of rule names that matched
      - final_action: the action to take (highest-priority rule wins)
      - escalation_reasons: list of human-readable reasons
      - overridden: True if the harness changed the agent's suggested action
    """
    fired      = []
    reasons    = []
    top_action = None
    top_prio   = -1

    for rule_fn in ALL_RULES:
        result = rule_fn(ticket, agent_output)
        if result:
            fired.append(result["rule"])
            reasons.append(result["reason"])
            prio = ACTION_PRIORITY.get(result["action"], 0)
            if prio > top_prio:
                top_prio   = prio
                top_action = result["action"]

    # If no rule fired, the agent's suggested action stands
    agent_action    = agent_output.get("suggested_action", "AUTO_SUGGEST_FIX")
    final_action    = top_action if top_action else agent_action
    was_overridden  = top_action is not None

    return {
        "rules_fired":          fired,
        "final_action":         final_action,
        "escalation_reasons":   reasons,
        "overridden":           was_overridden,
    }
