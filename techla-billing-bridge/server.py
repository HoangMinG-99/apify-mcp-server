"""Read-only Techla Apify account-usage MCP companion. Never starts an Actor.

The response is an ADVISORY preflight, not a transaction lock or proof of
prepaid balance. Use hard run caps and a separate aggregate run ledger.
"""
from __future__ import annotations

import hmac
import json
import math
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

APP_VERSION = "0.4.0"
MCP_VERSION = "2025-06-18"
APIFY_BASE = "https://api.apify.com/v2"
ALIAS_RE = re.compile(r"^[a-z][a-z0-9_]{0,50}$")
app = FastAPI(title="Techla Apify Billing Bridge", version=APP_VERSION,
              docs_url=None, redoc_url=None, openapi_url=None)


class CheckFailure(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def amount(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    n = float(value)
    return n if math.isfinite(n) and n >= 0 else None


def parse_date(value: Any) -> datetime:
    if not isinstance(value, str):
        raise CheckFailure("BAD_BILLING_CYCLE")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("Timezone missing")
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise CheckFailure("BAD_BILLING_CYCLE") from exc


def cycle_window(raw: Any, now: datetime) -> tuple[datetime, datetime]:
    if not isinstance(raw, dict):
        raise CheckFailure("BAD_BILLING_CYCLE")
    start, end = parse_date(raw.get("startAt")), parse_date(raw.get("endAt"))
    if not start <= now <= end or not start < end:
        raise CheckFailure("BILLING_CYCLE_STALE")
    return start, end


def secret_account(alias: str, link_id: str | None) -> tuple[str, str, str]:
    if not isinstance(alias, str) or not ALIAS_RE.fullmatch(alias):
        raise CheckFailure("BAD_ACCOUNT")
    suffix = alias.upper()
    token = os.getenv(f"APIFY_TOKEN_{suffix}", "")
    username = os.getenv(f"APIFY_EXPECTED_USERNAME_{suffix}", "").strip()
    mapped_link_id = os.getenv(f"APIFY_LINK_ID_{suffix}", "").strip()
    if not token or not username or not mapped_link_id:
        raise CheckFailure("ACCOUNT_NOT_CONNECTED")
    if not isinstance(link_id, str) or not link_id or not hmac.compare_digest(mapped_link_id, link_id):
        raise CheckFailure("LINK_ID_MISMATCH")
    return token, username, mapped_link_id


async def api_read(client: httpx.AsyncClient, token: str, path: str) -> dict:
    try:
        response = await client.get(f"{APIFY_BASE}{path}", headers={
            "Authorization": f"Bearer {token}", "Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise CheckFailure("APIFY_UNAVAILABLE") from exc
    if response.status_code == 401:
        raise CheckFailure("AUTH_INVALID")
    if response.status_code == 403:
        raise CheckFailure("INSUFFICIENT_SCOPE")
    if response.status_code == 429:
        raise CheckFailure("RATE_LIMIT")
    if not response.is_success:
        raise CheckFailure("API_ERROR", f"Apify HTTP {response.status_code}")
    try:
        data = response.json().get("data")
        if not isinstance(data, dict):
            raise ValueError("data missing")
        return data
    except (ValueError, TypeError, AttributeError) as exc:
        raise CheckFailure("BAD_RESPONSE") from exc


def blocked(reason: str, account: str, checked_at: str, *, username: str | None = None) -> dict:
    out = {"status": "BLOCKED", "reason": reason,
           "account_alias": account, "verified_at": checked_at}
    if username:
        out["apify_username"] = username
    return out


async def check_account_usage(account: str, planned_usd: float = 5.0,
                              phase_remaining_usd: float | None = None,
                              campaign_remaining_usd: float | None = None,
                              client: httpx.AsyncClient | None = None,
                              link_id: str | None = None) -> dict[str, Any]:
    """Fail-closed advisory gate, using API and independently verified ledger inputs."""
    now = datetime.now(timezone.utc)
    checked_at = now.isoformat()
    try:
        token, expected_username, mapped_link = secret_account(account, link_id)
    except CheckFailure as exc:
        return blocked(exc.reason, str(account), checked_at)

    fields = [amount(planned_usd), amount(phase_remaining_usd), amount(campaign_remaining_usd)]
    if any(x is None for x in fields) or fields[0] == 0:
        return blocked("CAMPAIGN_LEDGER_MISSING", account, checked_at)
    planned, phase_left, campaign_left = fields
    if planned > 5 or phase_left > 5 or campaign_left > 40:
        return blocked("CAMPAIGN_LIMIT_MISMATCH", account, checked_at)
    if planned > phase_left or planned > campaign_left:
        return blocked("INSUFFICIENT_CAMPAIGN_BUDGET", account, checked_at)

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10, follow_redirects=False)
    try:
        user = await api_read(client, token, "/users/me")
        username = user.get("username")
        if not isinstance(username, str) or username.casefold() != expected_username.casefold():
            raise CheckFailure("ACCOUNT_MISMATCH")
        limits = await api_read(client, token, "/users/me/limits")
        usage = await api_read(client, token, "/users/me/usage/monthly")

        limit_cycle = cycle_window(limits.get("monthlyUsageCycle"), now)
        usage_cycle = cycle_window(usage.get("usageCycle"), now)
        if any(abs((a-b).total_seconds()) > 2 for a, b in zip(limit_cycle, usage_cycle)):
            raise CheckFailure("BILLING_CYCLE_MISMATCH")

        policy, current, plan = limits.get("limits"), limits.get("current"), user.get("plan")
        if not all(isinstance(obj, dict) for obj in (policy, current, plan)):
            raise CheckFailure("BAD_BILLING_STRUCTURE")
        spent = amount(current.get("monthlyUsageUsd"))
        cap = amount(policy.get("maxMonthlyUsageUsd"))
        credits = amount(plan.get("monthlyUsageCreditsUsd"))
        reported_usage = amount(usage.get("totalUsageCreditsUsdAfterVolumeDiscount"))
        if spent is None or cap is None or reported_usage is None:
            raise CheckFailure("INCOMPLETE_BILLING")
        if abs(spent - reported_usage) > max(0.05, 0.03 * max(spent, reported_usage)):
            raise CheckFailure("USAGE_MISMATCH")
        if spent > cap + 0.0001:
            raise CheckFailure("HARD_LIMIT_EXCEEDED")

        allow_paid = os.getenv("APIFY_ALLOW_PAID_USAGE", "false").lower() == "true"
        hard_remaining = cap - spent
        free_remaining = max(0.0, credits - spent) if credits is not None else None
        if not allow_paid and free_remaining is None:
            raise CheckFailure("FREE_CREDIT_UNKNOWN")

        allowances = [hard_remaining, phase_left, campaign_left]
        if not allow_paid:
            allowances.append(free_remaining)
        left = max(0.0, min(allowances))
        pass_check = left + 0.00001 >= planned
        return {
            "status": "PASS" if pass_check else "BLOCKED",
            "reason": "WITHIN_VERIFIED_LIMITS" if pass_check else "INSUFFICIENT_VERIFIED_ALLOWANCE",
            "account_alias": account,
            "apify_username": username,
            "linked_apify_connection_id": mapped_link,
            "verified_at": checked_at,
            "usage_cycle": {"start_at": limits["monthlyUsageCycle"]["startAt"],
                            "end_at": limits["monthlyUsageCycle"]["endAt"]},
            "currency": "USD",
            "used_this_cycle_usd": round(spent, 4),
            "monthly_hard_limit_usd": round(cap, 4),
            "hard_limit_remaining_usd": round(max(0.0, hard_remaining), 4),
            "monthly_plan_credit_usd": round(credits, 4) if credits is not None else None,
            "free_credit_remaining_estimate_usd": round(free_remaining, 4) if free_remaining is not None else None,
            "paid_usage_permitted_by_bridge": allow_paid,
            "planned_usd": round(planned, 4),
            "phase_remaining_usd": round(phase_left, 4),
            "campaign_remaining_usd": round(campaign_left, 4),
            "bridge_available_allowance_usd": round(left, 4),
            "monthly_usage_after_discount_usd": round(reported_usage, 4),
            "guard_notice": "Read-only advisory; NOT actual prepaid balance or permission to spend. Must verify campaign ledger, serialize runs, use a native run-level charge cap, and reconcile each run before another.",
        }
    except CheckFailure as exc:
        return blocked(exc.reason, account, checked_at, username=expected_username if exc.reason != "ACCOUNT_MISMATCH" else None)
    finally:
        if owns_client:
            await client.aclose()


TOOL_DEF = {
    "name": "get_apify_account_usage",
    "description": "Read-only account billing; returns advisory PASS/BLOCKED, not run authorization. Does NOT trigger scraping.",
    "inputSchema": {
        "type": "object", "properties": {
            "account": {"type": "string", "description": "Configured account alias e.g. hung"},
            "link_id": {"type": "string", "description": "Exact ChatGPT Apify connection link_id"},
            "planned_usd": {"type": "number", "exclusiveMinimum": 0, "maximum": 5},
            "phase_remaining_usd": {"type": "number", "minimum": 0, "maximum": 5},
            "campaign_remaining_usd": {"type": "number", "minimum": 0, "maximum": 40},
        },
        "required": ["account", "link_id", "planned_usd", "phase_remaining_usd", "campaign_remaining_usd"],
        "additionalProperties": False,
    },
}


def rpc_result(reply_id: Any, value: dict | None = None, *, code: int | None = None,
               message: str = "") -> dict:
    if code is not None:
        return {"jsonrpc": "2.0", "id": reply_id,
                "error": {"code": code, "message": message}}
    return {"jsonrpc": "2.0", "id": reply_id, "result": value or {}}


@app.get("/")
async def index():
    return {"service": "Techla Apify Billing Bridge", "version": APP_VERSION,
            "notes": "Read-only. MCP endpoint /mcp; protected by Bearer secret."}


@app.get("/health")
async def health():
    return {"ok": True, "version": APP_VERSION}


@app.post("/mcp")
async def mcp(request: Request):
    headers = {"Cache-Control": "no-store"}
    secret = os.getenv("MCP_ACCESS_TOKEN", "")
    authorization = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(authorization, "Bearer " + secret):
        return JSONResponse({"error": "Unauthorized"}, status_code=401, headers=headers)
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        return JSONResponse(rpc_result(None, code=-32700, message="Parse error"), status_code=400, headers=headers)
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        return JSONResponse(rpc_result(None, code=-32600, message="Invalid JSON-RPC"), status_code=400, headers=headers)
    method, mid = body.get("method"), body.get("id")
    if method == "notifications/initialized":
        return Response(status_code=202, headers=headers)
    if mid is None:
        return JSONResponse(rpc_result(None, code=-32600, message="ID required"), status_code=400, headers=headers)
    if method == "initialize":
        response = {"protocolVersion": MCP_VERSION, "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "techla-apify-billing", "version": APP_VERSION}}
    elif method == "ping":
        response = {}
    elif method == "tools/list":
        response = {"tools": [TOOL_DEF]}
    elif method == "tools/call":
        params = body.get("params")
        if not isinstance(params, dict) or params.get("name") != TOOL_DEF["name"]:
            return JSONResponse(rpc_result(mid, code=-32602, message="Invalid tool"), headers=headers)
        arguments = params.get("arguments")
        if not isinstance(arguments, dict) or (set(arguments) != set(TOOL_DEF["inputSchema"]["required"])):
            return JSONResponse(rpc_result(mid, code=-32602, message="Invalid arguments"), headers=headers)
        result = await check_account_usage(**arguments)
        response = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                    "structuredContent": result, "isError": result.get("status") != "PASS"}
    else:
        return JSONResponse(rpc_result(mid, code=-32601, message="Method not found"), headers=headers)
    return JSONResponse(rpc_result(mid, response), headers=headers)
