# AI Ticket Triage Harness

**A portfolio project demonstrating AI governance, human-in-the-loop design, and audit trail generation in an IT helpdesk context.**

Built by [Kaitlyn Essel](https://github.com/kaitlynessel) as part of a portfolio for AI governance and healthcare IT roles.

---

## What It Does

This system reads synthetic IT support tickets, uses an AI agent to classify them, then passes every classification through a governance layer (the "harness") that enforces rules the AI cannot override — including patient safety escalations, PHI detection, and security incident response.

The output is a **summary table** of all tickets and an **audit log** that records every decision: what the AI said, which rules fired, and what actually happened.

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

---

## The Two Core Concepts: Agent vs. Harness

### The Agent
The agent is the AI doing the classification work. It reads a ticket and returns structured output:
- **Urgency**: critical / high / medium / low
- **Category**: network / hardware / software / access / security / other
- **Confidence**: how certain it is (0–100%)
- **Suggested fix**: plain-language troubleshooting step
- **Flags**: whether PHI or a security concern was detected

The agent runs in two modes:
- **Keyword mode** (default, no API key needed): uses pattern matching. Fast and free.
- **LLM mode**: uses Claude Haiku via the Anthropic API for richer reasoning. Set `ANTHROPIC_API_KEY` in `.env`.

### The Harness
The harness is everything *around* the agent that makes it safe and accountable. It runs after the agent and can override any decision. The rules are written to be readable by non-engineers — a compliance officer or manager can open `rules.py` and understand every policy.

> **This separation is the whole point.** The agent can be replaced or upgraded; the safety rules remain in place and can be audited independently.

---

## Governance Rules (`rules.py`)

Each rule has a name, a function, and a plain-language explanation of why it exists.

| Rule | Trigger | Action | Why |
|---|---|---|---|
| `RULE_CLINICAL_HIGH_URGENCY` | Clinical user (nurse, doctor, etc.) + high/critical urgency | Escalate immediately to human | Clinical IT failures can affect patient safety — never auto-resolve |
| `RULE_PHI_DETECTED` | Ticket mentions patient data, PHI, HIPAA, EHR, medical records | Escalate for HIPAA compliance review | HIPAA requires investigation and documentation of potential ePHI disclosures |
| `RULE_SECURITY_INCIDENT` | Ransomware, phishing, unauthorized access, credential theft | Escalate to security team immediately | Security incidents spread fast — a delayed response can encrypt an entire network |
| `RULE_LOW_CONFIDENCE` | AI confidence below 70% | Route to human reviewer | When the AI is uncertain, a human should decide — not the model |
| `RULE_NO_AUTO_CLOSE_CRITICAL` | User self-reported urgency as "critical" | Require human review | The user has context the AI doesn't — their self-assessment carries weight |

---

## Connection to AI Governance Frameworks

### NIST AI Risk Management Framework (AI RMF)
- **Govern 1.1** — Policies define what the AI is and isn't allowed to do. `rules.py` is that policy document.
- **Govern 1.7** — AI risk outcomes are documented. Every decision is written to `audit_log.jsonl`.
- **Measure 2.5** — Human oversight is required when AI confidence is low. `RULE_LOW_CONFIDENCE` enforces this.
- **Respond 1.1** — Incidents (security, PHI) are escalated, not auto-handled.

### Human-in-the-Loop (HITL) Design
This project is a concrete example of HITL: the AI handles clear, low-risk cases automatically, but any uncertainty, clinical risk, PHI involvement, or security concern routes to a human. The human doesn't review every ticket — only the ones where the stakes justify it.

### Auditability
Every decision is logged with: timestamp, ticket content, what the AI said, which rules fired, the final action, and the reason. This means a reviewer can reconstruct exactly what happened and why — the core requirement for responsible AI deployment in regulated industries.

### HIPAA Security Rule
The `RULE_PHI_DETECTED` rule implements a safeguard required under HIPAA §164.308(a)(1)(ii)(D): audit controls for systems that create, receive, transmit, or maintain ePHI. Any ticket touching patient data is escalated before any action is taken.

---

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

---

## How to Run

### 1. Clone and install

```bash
git clone https://github.com/kaitlynessel/ai-ticket-triage.git
cd ai-ticket-triage
pip install -r requirements.txt
```

### 2. (Optional) Add an API key for LLM classification

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

Without an API key, the system uses keyword-based classification — it still runs and enforces all the governance rules.

### 3. Run the demo

```bash
python3 main.py
```

You'll see each ticket processed in real time, a summary table, escalation reasons, and run statistics. The full audit log is written to `audit_log.jsonl`.

### 4. Inspect the audit log

```bash
# Pretty-print one entry
python3 -c "import json; [print(json.dumps(json.loads(l), indent=2)) for l in open('audit_log.jsonl')]" | head -60
```

---

## Synthetic Test Tickets

The 15 test tickets in `tickets/synthetic_tickets.json` cover:

| Ticket | Scenario | Expected escalation |
|---|---|---|
| TKT-001 | Nurse, VPN down before clinical shift | CLINICAL + PHI |
| TKT-003 | PHI potentially sent to wrong email | HIPAA review |
| TKT-004 | Staff clicked phishing link | SECURITY |
| TKT-005 | Physician: medication software crashed mid-order | IMMEDIATE (patient safety) |
| TKT-010 | Nurse: badge reader blocking medication room | IMMEDIATE (patient safety) |
| TKT-011 | Ransomware message on screen | SECURITY |
| TKT-007 | "Computer acting weird" (ambiguous) | KEYWORD: low confidence |
| TKT-014 | Radiologist: PACS slow but functional | Edge case: clinical but medium urgency |

---

## What I Learned Building This

- **Agent vs. harness separation** makes AI systems auditable. If you can't separate "what the AI did" from "what the system decided," you can't audit it.
- **Rules written in plain language** are more useful than technically clever ones. Compliance officers and department heads need to read them.
- **Confidence thresholds** are a governance decision, not just a technical one. Setting the threshold at 70% is a policy choice with real consequences for how many tickets go to humans.
- **This connects directly to WayFinder**: the same HITL principles I used for crisis detection in that project apply here — the AI handles what it's confident about; humans handle the rest.

---

## Related Project

This project extends the design principles from [2E WayFinder](https://github.com/kaitlynessel/2e-wayfinder), a neurodivergent care navigation prototype that uses the same human-in-the-loop and crisis-escalation design patterns.

---

*All ticket data is synthetic and fictional. No real patient, employee, or personal information was used.*
