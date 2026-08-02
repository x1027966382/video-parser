"""API 层测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["platforms"] >= 14


def test_platforms():
    r = client.get("/api/platforms")
    assert r.status_code == 200
    names = {p["name"] for p in r.json()["platforms"]}
    assert "bilibili" in names and "douyin" in names


def test_parse_invalid_url():
    r = client.post("/api/parse", json={"url": "https://example.com/abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False


def test_parse_missing_url():
    r = client.post("/api/parse", json={})
    assert r.status_code == 422


def test_parse_platform_unknown():
    r = client.post("/api/parse/notexist", json={"url": "https://a.com/b"})
    assert r.status_code == 200
    assert r.json()["success"] is False


def test_batch_empty():
    r = client.post("/api/batch", json={"urls": []})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_web_ui():
    assert client.get("/").status_code == 200
    assert client.get("/app.js").status_code == 200


def test_cookie_roundtrip():
    r = client.post("/api/cookie", json={"platform": "test", "cookie": "abc"})
    assert r.json()["ok"] is True
    r2 = client.get("/api/cookie")
    assert "test" in r2.json()
