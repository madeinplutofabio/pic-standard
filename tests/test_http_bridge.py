"""Tests for the PIC HTTP Bridge (sdk-python/pic_standard/integrations/http_bridge.py)."""

from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from pathlib import Path

import pytest

from pic_standard.policy import PICPolicy
from pic_standard.integrations.http_bridge import (
    handle_verify,
    PICBridgeServer,
    PICEvaluateLimits,
)


# ------------------------------------------------------------------
# Helpers (same pattern as test_mcp_guard_unit.py)
# ------------------------------------------------------------------

POLICY = PICPolicy(impact_by_tool={"payments_send": "money"})


def _proposal(trust: str) -> dict:
    return {
        "protocol": "PIC/1.0",
        "intent": "Send payment",
        "impact": "money",
        "provenance": [{"id": "invoice_123", "trust": trust, "source": "unit-test"}],
        "claims": [{"text": "Pay $500", "evidence": ["invoice_123"]}],
        "action": {"tool": "payments_send", "args": {"amount": 500}},
    }


def _verify(tool_name: str, tool_args: dict, policy: PICPolicy = POLICY) -> dict:
    """Shortcut: call handle_verify with sensible defaults."""
    return handle_verify(
        {"tool_name": tool_name, "tool_args": tool_args},
        policy=policy,
        limits=PICEvaluateLimits(),
        verify_evidence=False,
        proposal_base_dir=Path(".").resolve(),
        evidence_root_dir=None,
    )


# ------------------------------------------------------------------
# Unit tests (call handle_verify directly – no HTTP)
# ------------------------------------------------------------------


def test_bridge_blocks_missing_pic_for_money():
    result = _verify("payments_send", {"amount": 500})
    assert result["allowed"] is False
    assert result["error"]["code"].startswith("PIC_")


def test_bridge_blocks_untrusted_money():
    result = _verify("payments_send", {"amount": 500, "__pic": _proposal("untrusted")})
    assert result["allowed"] is False
    assert result["error"]["code"].startswith("PIC_")


def test_bridge_allows_trusted_money():
    result = _verify("payments_send", {"amount": 500, "__pic": _proposal("trusted")})
    assert result["allowed"] is True
    assert result["error"] is None
    assert isinstance(result["eval_ms"], int)


def test_bridge_blocks_tool_binding_mismatch():
    bad = _proposal("trusted")
    bad["action"]["tool"] = "some_other_tool"

    result = _verify("payments_send", {"amount": 500, "__pic": bad})
    assert result["allowed"] is False

    code = result["error"]["code"].upper()
    msg = result["error"]["message"].lower()
    assert "TOOL" in code and ("BIND" in code or "MISMATCH" in code)
    assert "tool" in msg and ("bind" in msg or "mismatch" in msg)


def test_bridge_missing_tool_name():
    result = handle_verify(
        {"tool_name": "", "tool_args": {}},
        policy=POLICY,
        limits=PICEvaluateLimits(),
        verify_evidence=False,
        proposal_base_dir=Path(".").resolve(),
        evidence_root_dir=None,
    )
    assert result["allowed"] is False
    assert "tool_name" in result["error"]["message"]


def test_bridge_missing_tool_args():
    result = handle_verify(
        {"tool_name": "payments_send", "tool_args": "not-a-dict"},
        policy=POLICY,
        limits=PICEvaluateLimits(),
        verify_evidence=False,
        proposal_base_dir=Path(".").resolve(),
        evidence_root_dir=None,
    )
    assert result["allowed"] is False
    assert "tool_args" in result["error"]["message"]


def test_bridge_no_detail_leakage_by_default(monkeypatch):
    monkeypatch.delenv("PIC_DEBUG", raising=False)

    result = _verify("payments_send", {"amount": 500, "__pic": _proposal("untrusted")})
    assert result["allowed"] is False
    assert "details" not in result.get("error", {})


def test_bridge_leaks_details_when_debug(monkeypatch):
    monkeypatch.setenv("PIC_DEBUG", "1")

    result = _verify("payments_send", {"amount": 500, "__pic": _proposal("untrusted")})
    assert result["allowed"] is False
    # Debug mode: response must still be well-formed regardless of detail presence.
    assert "code" in result["error"]
    assert "message" in result["error"]


# ------------------------------------------------------------------
# HTTP integration tests (start real server on random port)
# ------------------------------------------------------------------


@pytest.fixture()
def bridge_url():
    """Start a PICBridgeServer on a random port and yield its base URL."""
    server = PICBridgeServer(
        ("127.0.0.1", 0),  # port 0 = OS picks a free port
        policy=POLICY,
        verify_evidence=False,
    )
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def _http_post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _http_get(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def test_bridge_health_endpoint(bridge_url):
    result = _http_get(f"{bridge_url}/health")
    assert result == {"status": "ok"}


def test_bridge_http_allows_trusted(bridge_url):
    result = _http_post(
        f"{bridge_url}/verify",
        {"tool_name": "payments_send", "tool_args": {"amount": 500, "__pic": _proposal("trusted")}},
    )
    assert result["allowed"] is True
    assert result["error"] is None
    assert isinstance(result["eval_ms"], int)


def test_bridge_http_blocks_untrusted(bridge_url):
    result = _http_post(
        f"{bridge_url}/verify",
        {"tool_name": "payments_send", "tool_args": {"amount": 500, "__pic": _proposal("untrusted")}},
    )
    assert result["allowed"] is False
    assert result["error"]["code"].startswith("PIC_")


def test_bridge_http_malformed_json(bridge_url):
    req = urllib.request.Request(
        f"{bridge_url}/verify",
        data=b"this is not json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        pytest.fail("Expected HTTPError for malformed JSON")
    except urllib.error.HTTPError as e:
        assert e.code == 400
        result = json.loads(e.read())
        assert result["allowed"] is False
        assert result["error"]["code"] == "PIC_INVALID_REQUEST"


def test_bridge_http_not_found(bridge_url):
    req = urllib.request.Request(
        f"{bridge_url}/nonexistent",
        data=json.dumps({}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        pytest.fail("Expected 404")
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_bridge_http_method_not_allowed(bridge_url):
    req = urllib.request.Request(
        f"{bridge_url}/verify",
        method="DELETE",
    )
    try:
        urllib.request.urlopen(req)
        pytest.fail("Expected 405")
    except urllib.error.HTTPError as e:
        assert e.code == 405


# ------------------------------------------------------------------
# Content-Length and Body Size Validation
# ------------------------------------------------------------------

def _send_raw_http(bridge_url: str, headers: bytes, body: bytes = b"") -> str:
    """Send a raw HTTP request and return the response as a string.

    Useful for testing edge cases that urllib won't allow (missing headers,
    invalid Content-Length, etc.).
    """
    import socket

    # Parse host and port from bridge_url
    host_port = bridge_url.replace("http://", "")
    host, port_str = host_port.split(":")
    port = int(port_str)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.settimeout(5.0)
        s.sendall(headers + body)
        # Read response in chunks until connection closes
        chunks = []
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks).decode()


def test_bridge_http_missing_content_length(bridge_url):
    """Missing Content-Length header returns 400 with specific error message."""
    response = _send_raw_http(
        bridge_url,
        b"POST /verify HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Type: application/json\r\n"
        b"\r\n",
    )
    assert "400" in response
    assert "Missing Content-Length" in response


def test_bridge_http_empty_body(bridge_url):
    """Empty request body (Content-Length: 0) returns 400."""
    req = urllib.request.Request(
        f"{bridge_url}/verify",
        data=b"",
        headers={"Content-Type": "application/json", "Content-Length": "0"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        pytest.fail("Expected HTTPError for empty body")
    except urllib.error.HTTPError as e:
        assert e.code == 400
        result = json.loads(e.read())
        assert result["allowed"] is False
        assert result["error"]["code"] == "PIC_INVALID_REQUEST"
        assert "Empty request body" in result["error"]["message"]


def test_bridge_http_oversized_body(bridge_url):
    """Request body larger than MAX_REQUEST_BYTES returns 400."""
    from pic_standard.integrations.http_bridge import MAX_REQUEST_BYTES

    oversized_length = MAX_REQUEST_BYTES + 1
    response = _send_raw_http(
        bridge_url,
        b"POST /verify HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(oversized_length).encode() + b"\r\n"
        b"\r\n",
    )
    assert "400" in response
    assert "too large" in response
    assert str(MAX_REQUEST_BYTES) in response

def test_bridge_http_negative_content_length(bridge_url):
    """Negative Content-Length header returns 400."""
    response = _send_raw_http(
        bridge_url,
        b"POST /verify HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: -1\r\n"
        b"\r\n",
    )
    assert "400" in response
    assert "negative" in response.lower()


def test_bridge_http_malformed_content_length(bridge_url):
    """Non-numeric Content-Length header returns 400."""
    response = _send_raw_http(
        bridge_url,
        b"POST /verify HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: abc\r\n"
        b"\r\n",
    )
    assert "400" in response
    assert "Invalid Content-Length" in response


def test_bridge_http_non_dict_json_body(bridge_url):
    """JSON body that is not an object (array, string, number) returns 400."""
    test_cases = [
        (b'[1, 2, 3]', "list"),
        (b'"hello"', "str"),
        (b'123', "int"),
        (b'true', "bool"),
        (b'null', "NoneType"),
    ]
    for body, expected_type in test_cases:
        req = urllib.request.Request(
            f"{bridge_url}/verify",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            pytest.fail(f"Expected HTTPError for non-dict JSON body: {body}")
        except urllib.error.HTTPError as e:
            assert e.code == 400, f"Expected 400 for {body}, got {e.code}"
            result = json.loads(e.read())
            assert result["allowed"] is False
            assert result["error"]["code"] == "PIC_INVALID_REQUEST"
            assert "dict" in result["error"]["message"]
            assert expected_type in result["error"]["message"]
