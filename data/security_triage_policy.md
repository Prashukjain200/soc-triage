# Security Alert Triage Policy

*Internal reference for the alert-triage agent and the on-call security analyst.*

## 1. Purpose

This document governs how alerts are triaged: when an alert may be escalated,
when it may be dismissed, and when a human must sign off before any verdict is
final.

## 2. Evidence Required Before Any Verdict

Never decide from a single signal. Every alert must be checked against, at minimum:

- The user's baseline behavior (usual location, hours, device, role).
- The reputation of the IP involved.
- Other alerts related by IP, user, or time window (a cluster is a stronger
  signal than any single alert in isolation).
- For data-access events specifically: whether the resource accessed is normal
  for the user's role.

An alert should not be dismissed just because one of these checks came back
clean — all relevant checks must be consistent with a benign explanation.

## 3. Automatic Escalation Triggers

The following must always be escalated, regardless of how normal anything
else about the alert looks:

- Any login where MFA was not enforced or was bypassed, if the IP involved has
  any known-malicious reputation.
- Any login approved only after multiple consecutive MFA push-notification
  attempts (a push-bombing / "MFA fatigue" pattern) — the fact that MFA was
  eventually approved does **not** make this benign.
- Any bulk data export, or access to a resource outside the user's normal role
  scope, regardless of location, device, or MFA status.
- Any alert that correlates with two or more other alerts, across different
  users, within a short time window, from related IP ranges — treat this as a
  possible coordinated campaign and escalate all related alerts, even if each
  one individually looks minor.

## 4. Conditions That Support Dismissal

All of the following must hold — not just one — before an alert may be
considered for dismissal:

- The IP's reputation is clean, **and**
- The context is explained by one of: a documented approved travel note, a
  known company-sanctioned VPN provider, or a documented recent IT change
  (e.g. a newly provisioned device), **and**
- No related or clustered alerts were found, **and**
- No role/resource mismatch is present.

## 5. Human Sign-off Requirement

Escalating an alert never requires sign-off — escalation only costs analyst
time, so when in doubt, escalate. Dismissing one is the risky action, since a
wrongly dismissed alert is a missed breach. The agent must **not** close an
alert as dismissed without human sign-off if the alert involves any of:

- A known-malicious or unclassified/unrated IP.
- An MFA-fatigue pattern (multiple push attempts before approval).
- A bulk data export or any role/resource mismatch.

In these cases, even if the surrounding context looks explainable, the verdict
must be recorded as "pending human review," not closed outright.

## 6. Routine Noise — Do Not Escalate

A single failed login attempt followed by a successful one, from the same
device and IP the user always uses, is ordinary human error (a mistyped
password) and should not be escalated or held for review.
