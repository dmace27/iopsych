# Operational preparation

Prepared against `3602cb0` on 2026-11-04. This is bounded 12C preparation, not
release approval or a completed rehearsal. Reconcile these procedures against
the eventual integrated revision before execution. The authoritative scope and
unresolved decisions remain in
[the implementation plan](../../final-implementation-plan.md),
[the specification](../../mvp-spec.md) and the coordinator's
[progress ledger](../implementation/progress.md); this directory does not decide
6B policy.

- [Deployment and rollback](deployment-rollback.md)
- [Incidents and key rotation](incidents-keys.md)
- [Support, accommodations, rights and training](support-rights-training.md)
- [Retention, backup and deletion replay](retention-recovery.md)
- [Synthetic rehearsal and evidence matrix](synthetic-rehearsal.md)

**Current** means a command or API exists in the inspected revision; it does not
mean this worker executed it or that it satisfies a full package. **Gated**
means implementation, configuration, evidence or actual human approval is
missing. Every execution record must include revision, environment, UTC
timestamps, operator, exact command/test, result, skips and sanitized evidence
location. Never attach credentials, invite URLs, answers, exports or personal
data to ordinary tickets/logs.

| Responsibility                             | Assignment       | Required before release                                         |
| ------------------------------------------ | ---------------- | --------------------------------------------------------------- |
| Release engineering and database migration | owner-unassigned | Deployment access, compatibility decision and rollback evidence |
| Incident command and security response     | owner-unassigned | Responders, escalation route and alert receipt rehearsal        |
| Product/pilot owner                        | owner-unassigned | Pilot scope, stop/restart authority and actual launch decision  |
| Qualified I-O/content reviewer             | owner-unassigned | Revision-specific content/interpretation review                 |
| Privacy/legal reviewer                     | owner-unassigned | Applicable policy, verification, retention and rights decisions |
| Privacy administrator                      | owner-unassigned | Tenant-scoped authorized rights execution                       |
| Support/accommodation lead                 | owner-unassigned | Working contact and accessible alternative process              |
| Training/accessibility lead                | owner-unassigned | Training records and 12B findings                               |

These are required roles, not invented people or signoffs. No response SLA,
recovery objective, legal deadline or retention approval is established here.
Missing accountable owners and working contacts block real participant use.

This dispatch authorizes documentation only: no deployment, real mail, provider
purchase, production secrets or existing database reset. Any later local
rehearsal must use synthetic fixtures, deterministic extraction and controlled
loopback mail, with separate authorization for hosted actions. Reserved
resources for this work are web `3108`, API `8108`, PostgreSQL `5548`, database
`iopsych_runbooks`; none were started by this preparation.
