# Optional Apify Billing Bridge integration — legacy support

**Not required for lead scraping in Apify Tools v2.7.** The connected Apify App can discover, run cost-capped Actors and read datasets on its own. Do not require a Render deployment, an additional Apify token, or `get_apify_account_usage` before `call_actor`.

The companion is a separately hosted, read-only tool for users who **opt in** to additional billing diagnostics. Existing source is at `../assets/billing-bridge/`. It does not run inside ChatGPT just because the skill exists. It needs its own HTTPS MCP host, secure bearer authentication and per-account tokens installed in the hosting secret manager. The OAuth credentials of the existing Apify App are separate.

If opting in, read `../assets/billing-bridge/README_VI.md`, verify the real host, account mapping, current billing period, usage and limits. The values are advisory, not guaranteed prepaid credit or run authorization. Continue to protect each real run with its own native charge cap and the C03 campaign ledger.

If the bridge is missing or offline, **continue normal, authorized bounded scraping**; do not issue `BILLING_UNVERIFIED` as a blanket run ban.
