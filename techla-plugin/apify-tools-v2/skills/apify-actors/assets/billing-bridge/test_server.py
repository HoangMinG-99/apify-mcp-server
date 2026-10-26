"""Local regression suite; all Apify responses are mocks and cost USD 0."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
import httpx
import pytest
from fastapi.testclient import TestClient
import server

LINK = "link_6adad6d22e048191a1bca6794aaaed6f"


@pytest.fixture(autouse=True)
def secrets(monkeypatch):
    monkeypatch.setenv("MCP_ACCESS_TOKEN", "test-mcp-bearer-not-real")
    monkeypatch.setenv("APIFY_TOKEN_HUNG", "not-real-apify-token")
    monkeypatch.setenv("APIFY_EXPECTED_USERNAME_HUNG", "hung-demo")
    monkeypatch.setenv("APIFY_LINK_ID_HUNG", LINK)
    monkeypatch.setenv("APIFY_ALLOW_PAID_USAGE", "false")


def sample_data():
    now = datetime.now(timezone.utc)
    cycle = {"startAt": (now - timedelta(days=2)).isoformat(),
             "endAt": (now + timedelta(days=15)).isoformat()}
    return {
        "/v2/users/me": {"username": "hung-demo", "plan": {"monthlyUsageCreditsUsd": 10}},
        "/v2/users/me/limits": {"monthlyUsageCycle": cycle, "limits": {"maxMonthlyUsageUsd": 10},
                                 "current": {"monthlyUsageUsd": 2}},
        "/v2/users/me/usage/monthly": {"usageCycle": cycle,
                                        "totalUsageCreditsUsdAfterVolumeDiscount": 2},
    }


def run_with(payload, *, planned=5, phase=5, campaign=40, link=LINK, account="hung", status=200):
    def mock(req):
        assert req.headers["Authorization"] == "Bearer not-real-apify-token"
        return httpx.Response(status, json={"data": payload[req.url.path]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(mock)) as client:
            return await server.check_account_usage(account, planned, phase, campaign,
                                                    client=client, link_id=link)
    return asyncio.run(run())


def test_happy_path_read_only():
    result = run_with(sample_data())
    assert result["status"] == "PASS"
    assert result["bridge_available_allowance_usd"] == 5
    assert result["free_credit_remaining_estimate_usd"] == 8
    assert result["linked_apify_connection_id"] == LINK
    assert result["paid_usage_permitted_by_bridge"] is False
    assert "advisory" in result["guard_notice"].lower()


def test_missing_ledger_or_phase_budget_blocks():
    assert run_with(sample_data(), campaign=None)["reason"] == "CAMPAIGN_LEDGER_MISSING"
    assert run_with(sample_data(), phase=2)["reason"] == "INSUFFICIENT_CAMPAIGN_BUDGET"
    assert run_with(sample_data(), planned=6)["reason"] == "CAMPAIGN_LIMIT_MISMATCH"


def test_wrong_account_link_and_credential_blocks(monkeypatch):
    assert run_with(sample_data(), link="link_wrong")["reason"] == "LINK_ID_MISMATCH"
    monkeypatch.setenv("APIFY_EXPECTED_USERNAME_HUNG", "different-user")
    assert run_with(sample_data())["reason"] == "ACCOUNT_MISMATCH"
    monkeypatch.delenv("APIFY_TOKEN_HUNG")
    assert run_with(sample_data())["reason"] == "ACCOUNT_NOT_CONNECTED"


def test_bad_values_fail_closed():
    for bad in (float("nan"), float("inf"), -1, True, "5"):
        assert run_with(sample_data(), planned=bad)["status"] == "BLOCKED"
        assert run_with(sample_data(), phase=bad)["status"] == "BLOCKED"
    for bad in (None, 1, False):
        res = asyncio.run(server.check_account_usage("hung", 1, 5, 40, link_id=bad))
        assert res["status"] == "BLOCKED"


def test_negative_usage_is_not_clamped_to_zero():
    payload = sample_data()
    payload["/v2/users/me/limits"]["current"]["monthlyUsageUsd"] = -200
    assert run_with(payload)["reason"] == "INCOMPLETE_BILLING"


def test_cycle_stale_blocks():
    payload = sample_data()
    payload["/v2/users/me/limits"]["monthlyUsageCycle"] = {
        "startAt": "2020-01-01T00:00:00Z", "endAt": "2020-02-01T00:00:00Z"}
    assert run_with(payload)["reason"] == "BILLING_CYCLE_STALE"


def test_cycle_mismatch_blocks():
    payload = sample_data()
    now = datetime.now(timezone.utc)
    payload["/v2/users/me/usage/monthly"]["usageCycle"] = {
        "startAt": (now-timedelta(days=4)).isoformat(),
        "endAt": (now+timedelta(days=15)).isoformat()}
    assert run_with(payload)["reason"] == "BILLING_CYCLE_MISMATCH"


def test_usage_discrepancy_blocks():
    payload = sample_data()
    payload["/v2/users/me/usage/monthly"]["totalUsageCreditsUsdAfterVolumeDiscount"] = 7
    assert run_with(payload)["reason"] == "USAGE_MISMATCH"


def test_incomplete_billing_fails_closed():
    payload = sample_data()
    payload["/v2/users/me/limits"]["limits"].pop("maxMonthlyUsageUsd")
    assert run_with(payload)["reason"] == "INCOMPLETE_BILLING"


def test_no_free_credit_silently_allowed():
    payload = sample_data()
    payload["/v2/users/me"].pop("plan")
    assert run_with(payload)["reason"] == "BAD_BILLING_STRUCTURE"


def test_hard_cap_blocks_even_with_credit():
    payload = sample_data()
    payload["/v2/users/me/limits"]["limits"]["maxMonthlyUsageUsd"] = 3
    assert run_with(payload)["reason"] == "INSUFFICIENT_VERIFIED_ALLOWANCE"


def test_apify_401_blocks():
    def mock(req): return httpx.Response(401, json={"error": {"type": "invalid-token"}})
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(mock)) as client:
            return await server.check_account_usage("hung", 5, 5, 40, client=client, link_id=LINK)
    assert asyncio.run(go())["reason"] == "AUTH_INVALID"


def test_mcp_auth_initialize_list_and_call(monkeypatch):
    async def no_network_api(*args, **kwargs):
        raise server.CheckFailure("APIFY_UNAVAILABLE")
    monkeypatch.setattr(server, "api_read", no_network_api)
    with TestClient(server.app) as client:
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        assert client.post("/mcp", json=req).status_code == 401
        headers = {"Authorization": "Bearer test-mcp-bearer-not-real"}
        res = client.post("/mcp", json=req, headers=headers)
        assert res.status_code == 200
        assert res.json()["result"]["tools"][0]["name"] == "get_apify_account_usage"
        init = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}}, headers=headers)
        assert init.json()["result"]["protocolVersion"] == server.MCP_VERSION
        call = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "get_apify_account_usage", "arguments": {"account": "hung", "link_id": LINK, "planned_usd": 5,
              "phase_remaining_usd": 5, "campaign_remaining_usd": 40}}}, headers=headers)
        assert call.status_code == 200
        assert call.json()["result"]["structuredContent"]["status"] == "BLOCKED"  # mocked offline failure
        assert client.post("/mcp", json={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
            "name": "get_apify_account_usage", "arguments": {"account": "hung"}}}, headers=headers).json()["error"]["code"] == -32602
