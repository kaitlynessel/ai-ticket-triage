# AI Ticket Triage Harness

A portfolio project on AI governance, human-in-the-loop (HITL) design, and audit trail generation in an IT helpdesk setting. I built it as part of my portfolio for AI governance and healthcare IT roles.

## What It Does

The system reads synthetic IT support tickets and uses an AI agent to classify each one. Every classification then passes through a governance layer I call the harness. The harness enforces rules the AI cannot override, including patient safety escalations, PHI detection, and security incident response.

The output is a summary table of all tickets and an audit log that records every decision: what the AI said, which rules fired, and what actually happened.

```
Ticket
  │
  ▼
Agent (agent.py) ──── classifies urgency, category, confidence
  │
  ▼
Harness (harness.py) ─ applies governance rules from rules.py
  │
  ▼
Audit Log ──────────── records every decision (audit_log.jsonl)
  │
  ▼
Summary output to terminal
```

## The Two Core Concepts: Agent vs. Harness

### The Agent

The agent is the AI doing the classification work. It reads a ticket and returns structured output:

- **Urgency:** critical / high / medium / low
- **Category:** network / hardware / software / access / security / other
- **Confidence:** how certain it is (0 to 100%)
- **Suggested fix:** a plain-language troubleshooting step
- **Flags:** whether PHI or a security concern was detected

The agent runs in two modes:

- **Keyword mode (default, no API key needed):** uses pattern matching. It is fast and free.
- **LLM mode:** uses Claude Haiku through the Anthropic API for richer reasoning. Set `ANTHROPIC_API_KEY` in `.env`.

### The Harness

The harness is everything around the agent that makes it safe and accountable. It runs after the agent and can override any decision. I wrote the rules so a non-engineer can read them. A compliance officer or department manager should be able to open `rules.py` and understand every policy.

This separation is the whole point. The agent can be replaced or upgraded, and the safety rules stay in place and can be audited on their own.

## Governance Rules (`rules.py`)

Each rule has a name, a function, and a plain-language explanation of why it exists.

| Rule | Trigger | Action | Why |
|------|---------|--------|-----|
| `RULE_CLINICAL_HIGH_URGENCY` | Clinical user (nurse, doctor, etc.) with high or critical urgency | Escalate immediately to a human | Clinical IT failures can affect patient safety, so these are never auto-resolved |
| `RULE_PHI_DETECTED` | Ticket mentions patient data, PHI, HIPAA, EHR, or medical records | Escalate for HIPAA compliance review | HIPAA requires investigation and documentation of potential ePHI disclosures |
| `RULE_SECURITY_INCIDENT` | Ransomware, phishing, unauthorized access, or credential theft | Escalate to the security team immediately | Security incidents spread fast, and a delayed response can encrypt an entire network |
| `RULE_LOW_CONFIDENCE` | AI confidence below 70% | Route to a human reviewer | When the AI is uncertain, a human should make the decision |
| `RULE_NO_AUTO_CLOSE_CRITICAL` | User self-reported urgency as "critical" | Require human review | The user has context the AI does not, so their own assessment carries weight |

## Connection to AI Governance Frameworks

### NIST AI Risk Management Framework (AI RMF)

- **Govern:** Policies define what the AI is and is not allowed to do. `rules.py` is that policy document, and it assigns human oversight where the stakes are high.
- **Measure:** Confidence is tracked for every classification, and low confidence triggers human review through `RULE_LOW_CONFIDENCE`.
- **Manage:** Incidents involving security or PHI are escalated to people instead of being handled automatically, and every decision is written to `audit_log.jsonl`.

### Human-in-the-Loop (HITL) Design

The AI handles clear, low-risk cases automatically. Any uncertainty, clinical risk, PHI involvement, or security concern routes to a human. A person does not review every ticket, only the ones where the stakes justify it.

### Auditability

Every decision is logged with a timestamp, the ticket content, what the AI said, which rules fired, the final action, and the reason. A reviewer can reconstruct exactly what happened and why. That is the core requirement for responsible AI deployment in regulated industries.

### HIPAA Security Rule

`RULE_PHI_DETECTED` supports the audit control safeguards in the HIPAA Security Rule (45 CFR §164.312(b)) for systems that create, receive, transmit, or maintain ePHI. Any ticket touching patient data is escalated before any action is taken.

## Project Structure

```
ai-ticket-triage/
├── rules.py                   ← Governance rules (the most important file)
├── agent.py                   ← AI classification agent
├── harness.py                 ← Orchestrator: connects agent → rules → audit log
├── audit_log.py               ← Append-only decision log (JSONL format)
├── main.py                    ← Demo runner
├── config.py                  ← Settings and thresholds
├── tickets/
│   └── synthetic_tickets.json ← 15 test tickets (fake data, no real PII)
├── audit_log.jsonl            ← Generated on each run (not committed to git)
├── requirements.txt
├── .env.example
└── README.md
```

## How to Run

**1. Clone and install**

```bash
git clone https://github.com/kaitlynessel/ai-ticket-triage.git
cd ai-ticket-triage
pip install -r requirements.txt
```

**2. (Optional) Add an API key for LLM classification**

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

Without an API key, the system uses keyword-based classification. It still runs and enforces all the governance rules.

**3. Run the demo**

```bash
python3 main.py
```

You will see each ticket processed in real time, a summary table, escalation reasons, and run statistics. The full audit log is written to `audit_log.jsonl`.

**4. Inspect the audit log**

```bash
# Pretty-print one entry
python3 -c "import json; [print(json.dumps(json.loads(l), indent=2)) for l in open('audit_log.jsonl')]" | head -60
```

## Synthetic Test Tickets

The 15 test tickets in `tickets/synthetic_tickets.json` cover a range of scenarios. These are the ones I use most to show how the rules behave:

| Ticket | Scenario | Expected escalation |
|--------|----------|---------------------|
| TKT-001 | Nurse, VPN down before a clinical shift | CLINICAL + PHI |
| TKT-003 | PHI potentially sent to the wrong email | HIPAA review |
| TKT-004 | Staff member clicked a phishing link | SECURITY |
| TKT-005 | Physician: medication software crashed mid-order | IMMEDIATE (patient safety) |
| TKT-010 | Nurse: badge reader blocking the medication room | IMMEDIATE (patient safety) |
| TKT-011 | Ransomware message on screen | SECURITY |
| TKT-007 | "Computer acting weird" (ambiguous) | KEYWORD: low confidence |
| TKT-014 | Radiologist: PACS slow but functional | Edge case: clinical but medium urgency |

## What I Learned Building This

- **Separating the agent from the harness makes an AI system auditable.** If you cannot separate what the AI did from what the system decided, you cannot audit it.
- **Rules written in plain language are more useful than technically clever ones.** Compliance officers and department heads need to be able to read them.
- **A confidence threshold is a governance decision, not only a technical one.** Setting it at 70% is a policy choice with real consequences for how many tickets go to humans.
- **This connects directly to WayFinder.** The HITL principles I used for crisis detection there apply here too. The AI handles what it is confident about, and humans handle the rest.

This project has only been run on 15 synthetic tickets, and the default keyword mode is simple pattern matching. It is a portfolio demonstration, not a production system.

The safety rules stay in place even when the model changes.

## Related Project

This project extends the design principles from **2E WayFinder**, a neurodivergent care navigation prototype that uses the same human-in-the-loop and crisis-escalation design patterns.

All ticket data is synthetic and fictional. No real patient, employee, or personal information was used.
