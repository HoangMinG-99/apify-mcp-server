"""Techla Spa read-only Apify billing MCP bridge.

Provides an HTTP MCP endpoint backed by Apify's documented v2 account endpoints.
All Apify credentials are supplied by the hosting provider's secret manager.
Stateless, read-only, no Actor runs, no token output.
"""
from __future__ import annotations

import hmac
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

APP_VERSION = "0.3.0"
MCP_VERSION = "2025-06-18"
APIFY_BASE = "https://api.apify.com/v2"
VALID_ALIAS = re.compile(r"^[a-z][a-z0-9_]{0,50}$")
app = FastAPI(title="Techla Apify Billing Bridge", version=APP_VERSION, docs_url=None, redoc_url=None, openapi_url=None)


class CheckFailure(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    if value != value or value in (float("inf"), -float("inf")):
        return None
    return value


def _nonneg(value: Any) -> float | None:
    n = _number(value)
    return n if n is not None and n >= 0 else None


def _jsonrpc(reply_id: Any, result: dict[str, Any] | None = None, *, code: int | None = None, message: str = "") -> dict[str, Any]:
    if code is not None:
        return {"jsonrpc": "2.0", "id": reply_id, "error": {"code": code, "message": message}}
    return {"jsonrpc": "2.0", "id": reply_id, "result": result or {}}


def _token_for_alias(alias: str) -> tuple[str, str, str | None]:
    if not VALID_ALIAS.fullmatch(alias):
        raise CheckFailure("BAD_ACCOUNT", "Account alias is invalid")
    suffix = alias.upper()
    token = os.getenv(f"APIFY_TOKEN_{suffix}", "")
    expected = os.getenv(f"APIFY_EXPECTED_USERNAME_{suffix}", "")
    linked = os.getenv(f"APIFY_LINK_ID_{suffix}", "").strip() or None
    if not token or not expected:
        raise CheckFailure("ACCOUNT_NOT_CONNECTED", "Token or expected Apify username is not configured for this account")
    return token, expected, linked


async def _get_data(client: httpx.AsyncClient, token: str, path: str) -> dict[str, Any]:
    try:
        resp = await client.get(f"{APIFY_BASE}{path}", headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise CheckFailure("APIFY_UNAVAILABLE", "Apify API is unreachable") from exc
    if resp.status_code == 401:
        raise CheckFailure("AUTH_INVALID", "Apify credentials are invalid or expired")
    if resp.status_code == 403:
        raise CheckFailure("INSUFFICIENT_SCOPE", "Apify credential cannot read account billing")
    if resp.status_code == 429:
        raise CheckFailure("RATE_LIMIT", "Apify API rate limit; retry later")
    if not resp.is_success:
        raise CheckFailure("API_ERROR", f"Apify API returned HTTP {resp.status_code}")
    try:
        payload = resp.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            raise ValueError("Missing data")
        return payload["data"]
    except ValueError as exc:
        raise CheckFailure("BAD_RESPONSE", "Unexpected Apify API response") from exc


async def check_account_usage(
    account: str,
    planned_usd: float = 5.0,
    phase_remaining_usd: float | None = None,
    campaign_remaining_usd: float | None = None,
    client: httpx.AsyncClient | None = None,
    link_id: str | None = None,
) -> dict[str, Any]:
    """Advisory decision only. Spend guard also belongs on individual Actor runs.

    Phase/campaign remaining values MUST be grounded by user's central ledger.
    If either is unknown, do not approve new charges.
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    if not isinstance(account, str):
        return {"status": "BLOCKED", "reason": "BAD_ACCOUNT", "verified_at": checked_at}
    try:
        token, expected, linked = _token_for_alias(account)
        if not linked or link_id != linked:
            raise CheckFailure("LINK_ID_MISMATCH", "Exact Apify connection link_id must match secure account mapping")
    except CheckFailure as e:
        return {"status": "BLOCKED", "reason": e.code, "detail": e.detail, "account_alias": account, "verified_at": checked_at}

    amounts = [planned_usd, phase_remaining_usd, campaign_remaining_usd]
    if any(_number(n) is None or _number(n) < 0 for n in amounts) or planned_usd <= 0:
        return {"status": "BLOCKED", "reason": "CAMPAIGN_LEDGER_MISSING", "detail": "Provide numeric planned_usd, phase_remaining_usd and campaign_remaining_usd from the actual campaign ledger", "account_alias": account, "verified_at": checked_at}
    if planned_usd > 5.0 or phase_remaining_usd > 5.0 or campaign_remaining_usd > 40.0:
        return {"status": "BLOCKED", "reason": "CAMPAIGN_LIMIT_MISMATCH", "account_alias": account, "verified_at": checked_at}
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=10.0, follow_redirects=False)
    try:
        # No simultaneous credential reuse across linked Apify accounts.
        user = await _get_data(client, token, "/users/me")
        actual_username = user.get("username")
        if not isinstance(actual_username, str) or actual_username.lower() != expected.lower():
            raise CheckFailure("ACCOUNT_MISMATCH", "API token belongs to another Apify account")
        limits = await _get_data(client, token, "/users/me/limits")
        usage = await _get_data(client, token, "/users/me/usage/monthly")
    except CheckFailure as e:
        return {"status": "BLOCKED", "reason": e.code, "detail": e.detail, "account_alias": account, "verified_at": checked_at}
    finally:
        if own_client:
            await client.aclose()

    current = limits.get("current") or {}
    if not isinstance(current, dict): current = {}
    policy = limits.get("limits") or {}
    cycle = limits.get("monthlyUsageCycle") or {}
    plan = user.get("plan") or {}
    if not all(isinstance(v, dict) for v in (policy, cycle, plan)):
        return {"status": "BLOCKED", "reason": "BAD_BILLING_STRUCTURE", "account_alias": account, "verified_at": checked_at}
    spent = _nonneg(current.get("monthlyUsageUsd"))
    hard_cap = _nonneg(policy.get("maxMonthlyUsageUsd"))
    credits = _nonneg(plan.get("monthlyUsageCreditsUsd"))
    if spent is None or hard_cap is None or not cycle.get("startAt") or not cycle.get("endAt"):
        return {"status": "BLOCKED", "reason": "INCOMPLETE_BILLING", "account_alias": account, "apify_username": actual_username, "verified_at": checked_at}

    try:
        started = datetime.fromisoformat(str(cycle["startAt"]).replace("Z", "+00:00"))
        ended = datetime.fromisoformat(str(cycle["endAt"]).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if not (started <= now <= ended):
            return {"status": "BLOCKED", "reason": "BILLING_CYCLE_STALE", "account_alias": account, "apify_username": actual_username, "verified_at": checked_at}
    except (ValueError, TypeError, KeyError):
        return {"status": "BLOCKED", "reason": "BAD_BILLING_CYCLE", "account_alias": account, "verified_at": checked_at}

    hard_remaining = max(0.0, hard_cap - spent)
    free_remaining = max(0.0, credits - spent) if credits is not None else None
    allow_paid = os.getenv("APIFY_ALLOW_PAID_USAGE", "false").strip().lower() == "true"
    # Explicitly approve paid overage in the hosting environment. Never imply a plan is prepaid.
    components = [hard_remaining, phase_remaining_usd, campaign_remaining_usd]
    if not allow_paid:
        if free_remaining is None:
            return {"status": "BLOCKED", "reason": "FREE_CREDIT_UNKNOWN", "account_alias": account, "apify_username": actual_username, "verified_at": checked_at}
        components.append(free_remaining)
    safe_remaining = min(components)
    can_run = safe_remaining >= planned_usd
    result: dict[str, Any] = {
        "status": "PASS" if can_run else "BLOCKED",
        "reason": "WITHIN_VERIFIED_LIMITS" if can_run else "INSUFFICIENT_VERIFIED_ALLOWANCE",
        "account_alias": account,
        "apify_username": actual_username,
        "linked_apify_connection_id": linked,
        "verified_at": checked_at,
        "usage_cycle": {"start_at": cycle["startAt"], "end_at": cycle["endAt"]},
        "currency": "USD",
        "used_this_cycle_usd": round(spent, 4),
        "monthly_hard_limit_usd": round(hard_cap, 4),
        "hard_limit_remaining_usd": round(hard_remaining, 4),
        "monthly_plan_credit_usd": round(credits, 4) if credits is not None else None,
        "free_credit_remaining_estimate_usd": round(free_remaining, 4) if free_remaining is not None else None,
        "paid_usage_permitted_by_bridge": allow_paid,
        "planned_usd": round(planned_usd, 4),
        "phase_remaining_usd": round(phase_remaining_usd, 4),
        "campaign_remaining_usd": round(campaign_remaining_usd, 4),
        "bridge_available_allowance_usd": round(safe_remaining, 4),
        "monthly_usage_after_discount_usd": _nonneg(usage.get("totalUsageCreditsUsdAfterVolumeDiscount")),
        "guard_notice": "This is an advisory read-only check. Require maxTotalChargeUsd or equivalent on each Actor run and recheck after each run. Linked account identity and CRM ledger are independent inputs.",
    }
    return result


TOOL_DEF = {
    "name": "get_apify_account_usage",
    "description": "Read account-specific Apify billing and test C03 MASS budget allowance without starting Actors. Uses a server-stored Apify token, not the caller's Apify connection token.",
    "inputSchema": {"type": "object", "properties": {
        "account": {"type": "string", "description": "Configured account alias, e.g. hung"},
        "link_id": {"type": "string", "description": "Exact Apify link_id from the current ChatGPT connection, e.g. link_..."},
        "planned_usd": {"type": "number", "minimum": 0.01, "maximum": 5.0},
        "phase_remaining_usd": {"type": "number", "minimum": 0, "maximum": 5},
        "campaign_remaining_usd": {"type": "number", "minimum": 0, "maximum": 40},
    }, "required": ["account", "link_id", "planned_usd", "phase_remaining_usd", "campaign_remaining_usd"], "additionalProperties": False},
}


@app.get("/")
async def index():
    return {"service": "Apify Billing Bridge", "version": APP_VERSION, "notes": "MCP endpoint: /mcp; read-only; configure secrets in hosting dashboard"}


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    headers = {"Cache-Control": "no-store"}
    secret = os.getenv("MCP_ACCESS_TOKEN", "")
    actual_auth = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(actual_auth, "Bearer " + secret):
        return JSONResponse({"error": "Unauthorized"}, status_code=401, headers=headers)
    try:
        msg = await request.json()
        if not isinstance(msg, dict):
            raise ValueError("JSON object required")
    except (ValueError, json.JSONDecodeError):
        return JSONResponse(_jsonrpc(None, code=-32700, message="Parse error"), status_code=400, headers=headers)
    mid = msg.get("id")
    method = msg.get("method")
    if method == "notifications/initialized":
        return Response(status_code=202, headers=headers)
    if mid is None:
        return JSONResponse(_jsonrpc(None, code=-32600, message="Request id required"), headers=headers)
    if method == "initialize":
        result = {"protocolVersion": MCP_VERSION, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "techla-apify-billing", "version": APP_VERSION}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [TOOL_DEF]}
    elif method == "tools/call":
        params = msg.get("params") or {}
        if params.get("name") != TOOL_DEF["name"]:
            return JSONResponse(_jsonrpc(mid, code=-32602, message="Unknown tool"), headers=headers)
        args = params.get("arguments") or {}
        if not isinstance(args, dict) or any(k not in TOOL_DEF["inputSchema"]["properties"] for k in args):
            return JSONResponse(_jsonrpc(mid, code=-32602, message="Invalid arguments"), headers=headers)
        try:
            data = await check_account_usage(**args)
        except (TypeError, ValueError):
            return JSONResponse(_jsonrpc(mid, code=-32602, message="Invalid arguments"), headers=headers)
        result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}], "isError": data.get("status") != "PASS", "structuredContent": data}
    else:
        return JSONResponse(_jsonrpc(mid, code=-32601, message="Method not found"), headers=headers)
    return JSONResponse(_jsonrpc(mid, result), headers=headers)
