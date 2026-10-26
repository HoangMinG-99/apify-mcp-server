---
name: apify-acceptance
description: Verify end-to-end direct Apify Actor execution, cost caps, dataset extraction and CRM handoff for Techla Spa without requiring an external billing bridge.
---
# Apify Tools v2.7 — direct-run acceptance

Read `skills/apify-actors/SKILL.md` first. Evaluate the **existing linked Apify App**; do not treat the optional Billing Bridge as a prerequisite.

1. Confirm the exact plugin ID/release version and preserve `.app.json` binding and the existing authorized Apify account `link_id`.
2. Test `search_actors` and `fetch_actor_details` (read-only); verify up-to-date pricing and the Actor input schema. A successful Store query means only `ACTOR_DISCOVERY_OK`.
3. Check user approval, C03 phase/campaign reservations and remaining authorized spend. No need for `get_apify_account_usage`, Render, or separate API token; their absence must not mark the linked App unusable.
4. For pay-per-event Actors, apply `callOptions.maxTotalChargeUsd`; for pay-per-result Actors, apply `callOptions.maxItems`, bounded Actor inputs, and conservative cost calculation. If no meaningful cap can be enforced, choose another Actor, not an unbounded test.
5. Run a small explicitly approved scraping task (suggest $0.50 cap or lower) using the selected `link_id`. Verify `runId`, final status and real dataset ID; read dataset only from returned IDs and deduplicate against CRM.
6. Update CRM and log all new/no-new outcomes, run cap, new results, account ID and cost verified from the provider if available (otherwise `actual unknown`, reserve run cap). Do not claim an unverified actual USD amount.
7. If provider responds `limit exceeded`, `payment required`, or credit exhausted, report that exact condition. A failed attempt is not a successful paid run. Never switch accounts to bypass provider restrictions.

Statuses: `ACTOR_DISCOVERY_OK` → `ACTOR_RUN_SUCCEEDED` → `DATASET_RETRIEVED` → `CRM_WRITTEN` → `COST_RECONCILED`. Optional bridge acceptance uses its own infrastructure/diagnostics statuses, separate from this chain.

Keep tokens/secrets out of chat and CRM. No screenshots required when the linked Apify App can execute normally.
