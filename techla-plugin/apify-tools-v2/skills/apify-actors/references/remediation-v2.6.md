# Legacy remediation note from v2.6 (superseded by v2.7)

## History

Apify Tools v2.6 required a separately deployed billing companion and blocked all paid Actor runs if `get_apify_account_usage` was not connected. This created a recurring operational blocker although the existing Apify App already exposes native run-cost controls.

## Current v2.7 policy

**The mandatory Billing Bridge gate has been retired.** Do not interpret previous v2.6 `BILLING_UNVERIFIED` notes or missing Render deployment as grounds to stop a duly authorized, capped run. Follow `skills/apify-actors/SKILL.md` and use the existing authorized App directly.

Continue protecting spend with approved C03 ceilings ($5 per batch, $40 across campaign), `maxTotalChargeUsd` for pay-per-event Actors or `maxItems` for pay-per-result Actors, serialized runs, conservative ledger reservations, and honest cost reconciliation. A provider account hard limit remains authoritative; never evade provider restrictions.

The optional bridge source can still be used for diagnostics on explicit user request. It has not been deployed or implicitly connected by this update.
