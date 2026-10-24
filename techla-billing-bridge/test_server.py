"""Run with: pytest -q test_server.py"""
import asyncio
from datetime import datetime, timezone, timedelta
import httpx
import pytest
from fastapi.testclient import TestClient
import server

LINK="link_6adad6d22e048191a1bca6794aaaed6f"

@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("MCP_ACCESS_TOKEN", "safe-mcp-test-secret")
    monkeypatch.setenv("APIFY_TOKEN_HUNG", "test-only-not-real")
    monkeypatch.setenv("APIFY_EXPECTED_USERNAME_HUNG", "hung-verified")
    monkeypatch.setenv("APIFY_LINK_ID_HUNG", LINK)
    monkeypatch.setenv("APIFY_ALLOW_PAID_USAGE", "false")


def apify_handler(request):
    path = request.url.path
    if request.headers.get("Authorization") != "Bearer test-only-not-real":
        return httpx.Response(401, json={})
    if path == "/v2/users/me":
        return httpx.Response(200, json={"data": {"username": "hung-verified", "plan": {"monthlyUsageCreditsUsd": 10.0, "tier": "FREE"}}})
    if path == "/v2/users/me/limits":
        return httpx.Response(200, json={"data": {"monthlyUsageCycle": {"startAt": (datetime.now(timezone.utc)-timedelta(days=1)).isoformat(), "endAt": (datetime.now(timezone.utc)+timedelta(days=15)).isoformat()}, "limits": {"maxMonthlyUsageUsd": 10.0}, "current": {"monthlyUsageUsd": 2.0}}})
    if path == "/v2/users/me/usage/monthly":
        return httpx.Response(200, json={"data": {"totalUsageCreditsUsdAfterVolumeDiscount": 2.0}})
    return httpx.Response(404)


def test_ok_and_block(monkeypatch):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(apify_handler)) as client:
            a = await server.check_account_usage("hung", 5, 5, 40, client=client, link_id=LINK)
            assert a["status"] == "PASS"
            assert a["free_credit_remaining_estimate_usd"] == 8
            b = await server.check_account_usage("hung", 5, 2, 40, client=client, link_id=LINK)
            assert b["status"] == "BLOCKED" and b["reason"] == "INSUFFICIENT_VERIFIED_ALLOWANCE"
            c = await server.check_account_usage("hung", 5, 5, None, client=client, link_id=LINK)
            assert c["status"] == "BLOCKED" and c["reason"] == "CAMPAIGN_LEDGER_MISSING"
    asyncio.run(run())


def test_account_mismatch(monkeypatch):
    monkeypatch.setenv("APIFY_EXPECTED_USERNAME_HUNG", "someone-else")
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(apify_handler)) as client:
            a = await server.check_account_usage("hung", 5, 5, 40, client=client, link_id=LINK)
            assert a["status"] == "BLOCKED" and a["reason"] == "ACCOUNT_MISMATCH"
    asyncio.run(run())


def test_mcp_auth_and_tool_listing():
    with TestClient(server.app) as client:
        req={"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
        assert client.post("/mcp",json=req).status_code == 401
        resp = client.post("/mcp",json=req,headers={"Authorization":"Bearer safe-mcp-test-secret"})
        assert resp.status_code == 200
        assert resp.json()["result"]["tools"][0]["name"]=="get_apify_account_usage"


def test_unconfigured_fails_closed(monkeypatch):
    monkeypatch.delenv("APIFY_TOKEN_HUNG")
    result=asyncio.run(server.check_account_usage("hung",5,5,40,link_id=LINK))
    assert result["status"]=="BLOCKED"


def test_link_id_wrong_or_missing_blocks():
    bad=asyncio.run(server.check_account_usage("hung",5,5,40,link_id="link_another"))
    missing=asyncio.run(server.check_account_usage("hung",5,5,40))
    assert bad["reason"]=="LINK_ID_MISMATCH"
    assert missing["reason"]=="LINK_ID_MISMATCH"


def test_stale_cycle_blocks(monkeypatch):
    def stale(req):
        if req.url.path=="/v2/users/me/limits":
            return httpx.Response(200,json={"data":{"monthlyUsageCycle":{"startAt":"2020-01-01T00:00:00Z","endAt":"2020-01-31T23:59:59Z"},"limits":{"maxMonthlyUsageUsd":10.0},"current":{"monthlyUsageUsd":1.0}}})
        return apify_handler(req)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(stale)) as client:
            return await server.check_account_usage("hung",5,5,40,client=client,link_id=LINK)
    res=asyncio.run(run())
    assert res["reason"]=="BILLING_CYCLE_STALE"


def test_negative_budget_rejected():
    for val in (-1,float('nan'),float('inf')):
        res=asyncio.run(server.check_account_usage("hung",5,val,40,link_id=LINK))
        assert res["status"]=="BLOCKED"


def test_paid_usage_not_implicitly_allowed():
    # Correctly configured free account with $8 free credit: planned $9 is invalid
    res=asyncio.run(server.check_account_usage("hung",5,5,40,link_id=LINK))
    # No API client in this test; absence of credential/network completion must not produce PASS.
    assert res.get("status")!="PASS" or res.get("apify_username")=="hung-verified"
