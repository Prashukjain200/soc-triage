# Security Alert Triage Agent — Approach

A LangChain agent that triages security alerts: given a raw alert, it gathers
evidence from several independent sources, decides whether it's a real threat
or noise, and either escalates it or dismisses it — with a human gate on the
side that actually matters.

## Why this project (vs. the others already built)

- **CiteRAG** — one document, retrieval + citation.
- **TicketOps** — one customer's narrative, judged against policy + their own
  refund history.
- **Invoice Matching** (not yet built) — two independently-authored documents
  reconciled against each other.
- **This one** — several *independent* signals (user's baseline behavior, IP
  reputation, related alerts, role/resource fit) that must be weighed
  *together*, since no single one is conclusive on its own. That's the
  differentiator: multi-signal correlation under uncertainty, not narrative
  judgment or document matching.

## The gate — and why it's flipped from TicketOps

In TicketOps, the risky action was *approving* something (a refund), so the
human gate sat on approval above a threshold. Here, the risky action is
**dismissing** an alert — declaring "nothing to see here" costs nothing if
you're wrong about escalating (an analyst just spends a few minutes on a
false alarm), but costs everything if you wrongly dismiss a real breach.

So the gate is on the *dismiss* path, not the *escalate* path: the agent may
freely escalate anything it's suspicious of, but it must **not** auto-close
an alert as dismissed — without a human signing off first — if the alert
involves a known-bad or unrated IP, an MFA-fatigue pattern, a bulk data
export, or a role/resource mismatch. See `data/security_triage_policy.md`
Section 5 for the exact rule.

## Data (`data/`)

| File | What it's for |
|---|---|
| `users.csv` | Baseline behavior per user: usual location/hours/device, role, MFA enrollment, and context notes (approved travel, recent IT changes) |
| `ip_reputation.csv` | Known-malicious IPs, one sanctioned corporate VPN pool, and clean office/residential IPs |
| `alerts.csv` | 4 already-resolved alerts (history to correlate against) + 8 pending alerts to triage |
| `security_triage_policy.md` | The escalation/dismissal rules — the agent's actual grounding text, same role `refund_policy.md` played for TicketOps |

### The 8 pending alerts and what each tests

| Alert | Scenario | Should resolve to |
|---|---|---|
| ALT-2001 | Login via legacy IMAP, MFA bypassed, IP is a known-malicious hosting range | Escalate — clear-cut |
| ALT-2002 | Same night, different user, same IP block as ALT-2001 | Escalate — tests whether the agent notices the *cluster*, not just one bad login |
| ALT-2003 | Odd-hours London login, but IP is clean and matches an approved-travel note | Dismiss |
| ALT-2004 | New IP within the sanctioned corporate VPN pool | Dismiss — normal VPN IP rotation |
| ALT-2005 | MFA *passed*, but only after 6 push-notification attempts, from a Tor exit node | Escalate — tests whether "MFA passed" alone gets wrongly treated as sufficient |
| ALT-2006 | Marketing Coordinator downloads 250k customer records — normal location/device/MFA | Escalate — anomaly is purely role/resource-based, not geographic |
| ALT-2007 | One failed login, then success, same device/IP | Dismiss without escalation — routine noise, not worth analyst time |
| ALT-2008 | Login from a brand-new device fingerprint | Dismiss — IT notes confirm a laptop was provisioned two days prior |

## Tools to build

1. `get_user_baseline(user_email)` — reads `users.csv`.
2. `check_ip_reputation(ip)` — reads `ip_reputation.csv`.
3. `check_related_alerts(ip=None, user=None, hours=24)` — reads `alerts.csv`,
   returns *raw* matching rows (by IP prefix / user / time window) — the
   agent has to notice a cluster itself, it isn't handed a pre-computed verdict.
4. `check_role_permissions(user_email, resource)` — cross-references a
   user's role/`typical_resources` against the resource actually accessed.
5. `resolve_alert(alert_id, verdict, notes)` — writes the final call back
   into `alerts.csv` (mirrors `write_decision` in TicketOps).

All five are deterministic lookups/writes — no LLM inside any of them. The
judgment (does this combination of facts add up to a threat?) is the agent's
job; the facts themselves are never something it's allowed to guess.

## System prompt — the one rule that matters most

Never issue a verdict from a single signal. Always check baseline behavior +
IP reputation + related alerts (+ role, for data-access events) before
deciding anything. Escalating costs nothing to get "wrong"; dismissing does.

## Build order (mirrors CiteRAG/TicketOps)

1. Load the three CSVs + the policy doc.
2. Build the five tools.
3. Write the system prompt.
4. Reuse the existing agent loop shape: `TOOLS_BY_NAME` dispatch,
   `while response.tool_calls and rounds < N`.
5. Loop over `alerts.csv` rows where `status == "pending"`, same shape as
   `run_tickets()` looping over pending tickets in TicketOps.
6. Where the agent wants to dismiss something on the gated list (Section 5 of
   the policy), hold it for a human `y/n` — same pattern as
   `ask_human_approval` in TicketOps, just gating the opposite action.
7. Run the 8 scenarios above before trusting it on anything else.
