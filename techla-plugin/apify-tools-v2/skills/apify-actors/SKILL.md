---
name: apify-actors
description: Find, safely run, audit, and deduplicate Apify Actors for Techla Spa using existing linked accounts and hard per-run cost caps; no mandatory billing bridge.
---
# Apify Tools v2 — direct bounded scraping (2.7)

**Operating rule:** Use the installed, authorized Apify App directly. The separate Billing Bridge / `get_apify_account_usage` is **OPTIONAL**. Its absence, a missing Render host, or lack of a separate Apify API token must **NEVER by itself block a previously approved, bounded Actor run**. Do not install, deploy, or insist on that companion to start a run. Still respect provider-imposed limits and the approved campaign budget.

## Select account and source

- Prefer the user's most recently selected linked account and pass its **exact `link_id`** to every Apify call. Label that account in the campaign log. Do not invent account ownership or infer its credit from another account's browser tab.
- Select a platform/source likely to yield Spa/Clinic owners/operators or verifiable businesses in Hanoi. Prefer evidence of direct operational needs over indiscriminate lead volume.
- `search_actors` / `fetch_actor_details` are discovery and price/schema preflight; discovery is not a run. Check both pricing model and input schema before paid execution.
- Check CRM/source registry for previously scraped URLs, place IDs, account profiles, and date windows. Do not rescrape completed coverage just because an account changed.

## Billable Actor workflow — WITHOUT bridge dependency

1. Require explicit authorization to spend. For Techla Spa C03, the user has previously approved **up to $5 per scraping batch and $40 across the campaign**. These are *ceiling permissions*, not evidence of account credit or automatically unspent funds. Respect later user updates and pause if limits are unclear.
2. Check the campaign run ledger and existing reservations to avoid double-counting and overlapping runs. Use separately recorded run costs; where a prior campaign run's actual cost cannot be verified, do not claim a precise remaining balance and conservatively count its authorized reserved cap until reconciled. Do not silently charge a separate historic dataset again.
3. **Enforce run cost in the Apify call itself:** For `PAY_PER_EVENT`, supply `callOptions.maxTotalChargeUsd` no greater than available approved phase/campaign amount. For `PAY_PER_RESULT`, supply `callOptions.maxItems`, compute a conservative USD ceiling from current pricing (including startup/add-on fees), and bound Actor input (`resultsLimit`, `maxResults`, search URLs, time/date, etc.). Caps for one billing model may be ignored for the other; do not substitute an estimated result count for an enforceable limit.
4. Start with a small, measurable run, typically no more than **$0.50 of the approved batch**, then scale from observed quality/cost. Never invoke `call_actor` just to test credentials or a balance; use it only for a real approved scraping purpose with suitable cost bounds. If the Actor does not expose a reliable enforceable cost bound for its pricing model, choose another Actor or use no-cost/manual source gathering; **this is a per-run cap issue, not a missing billing bridge issue**.
5. **Serialize charged runs.** Record link ID, Actor, input scope, cap, `runId`, dataset ID, number returned, status and actual cost when known. A Sheet log is not an atomic reservation. Reconcile each run before consuming further campaign budget; if actual cost is unavailable, retain the reserved cap as provisional spending.
6. When Apify returns `monthly usage limit exceeded`, payment/credit errors, or other provider denial: report this exact error. Never infer available credit, mislabel failed runs as paid successes, or switch accounts to evade a provider-imposed restriction. Switching to another user-authorized account is allowed only when consistent with Apify terms and shared campaign caps; track each source/account separately.
7. Read dataset only from a real returned ID accessible to the selected account. Deduplicate by Google Place ID, canonical profile/page URL, business phone, organization+address. Add records to CRM with original source link, collection time, validation status, duplicate result and source/run IDs. Keep unverified intent separate from actual Sales confirmation.

## Optional billing observability (not a gate)

- If a *connected and functional* `get_apify_account_usage` exists, it may provide supplementary billing diagnostics; it is **not required** for `call_actor` and its response is not spend consent, proof of prepaid balance, or an atomic lock.
- The legacy companion source under `assets/billing-bridge/` is **optional reference material**. It is not deployed just because the plugin was updated. Refer to its README only if the user **explicitly requests** billing infrastructure or bridge acceptance. Do not send users into a repeated Render/token setup workflow for ordinary lead scraping.

## Techla Spa lead-quality defaults

- Geographical priority: Spa/Clinic owners/operators near 71 Nguyễn Chí Thanh, Hà Nội; outer districts mainly for lower-priority community proof unless new conversion evidence supports expansion.
- Prioritize Facebook Group posts/comments that explicitly describe management pain or request advice, then Page/profile business verification, Maps gaps, Instagram, Threads and TikTok as appropriate.
- Hiring/expansion is an *investigation signal*, not proof the business wants AI/software. Do not label a lead hot unless Sales/customer evidence warrants it.
- Use public business contact details necessary for B2B validation. Never send sensitive internal budgets, partner rates, unapproved cases, private lists or nonpublic personal information to external Actors.
- Handoff columns: dated evidence, source URL, platform, business/decision-maker validation, public business contact, area, ICP fit, signal strength, Sales status, duplicate status, run/dataset IDs and actual/provisional USD.

If asked for acceptance, use `skills/apify-acceptance/SKILL.md`. Distinguish `ACTOR_DISCOVERY_OK`, `ACTOR_RUN_SUCCEEDED`, `DATASET_RETRIEVED`, `CRM_WRITTEN`, `COST_RECONCILED`. Do not claim any later state based on earlier ones.
