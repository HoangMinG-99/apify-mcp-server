# Optional Apify Billing Bridge — infrastructure checklist (not a scraping prerequisite)

**v2.7 note:** This checklist applies **only when the user explicitly requests deploying the optional account-usage reporting bridge**. Ordinary, authorized Actor runs go directly through the existing Apify App using native per-run cost caps. Missing Render/`get_apify_account_usage` is **not** an Actor execution blocker.

If optional bridge setup is requested:
1. Deploy the isolated read-only server in `assets/billing-bridge/` to a secured HTTPS host.
2. Configure `MCP_ACCESS_TOKEN` and account-specific `APIFY_TOKEN_<ALIAS>`, `APIFY_EXPECTED_USERNAME_<ALIAS>`, `APIFY_LINK_ID_<ALIAS>` via host secret manager (never chat/Sheets).
3. Connect the authenticated `/mcp` endpoint and verify live `/health`, `initialize`, `tools/list`, `tools/call`, then compare username/period/usage with the intended account.
4. Distinguish `SOURCE_READY`, `TESTED_MOCK`, `DEPLOYED`, `CONNECTED`, `BILLING_VERIFIED`. These are **optional bridge statuses only**.
5. Never claim a mock test proves actual credit or account ownership. Bridge results are advisory, not a transaction lock.

For any paid Actor run independently apply `maxTotalChargeUsd` or `maxItems` according to pricing and the approved campaign ledger. If a model cannot enforce a per-run cap, choose another Actor; this requirement does not depend on Bridge deployment.
