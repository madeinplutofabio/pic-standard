"""
PIC HTTP Bridge – lightweight verification server for non-Python integrations.

Wraps ``evaluate_pic_for_tool_call()`` from the MCP guard module and exposes
it over HTTP so that TypeScript / Go / etc. consumers can verify PIC proposals
without shelling out to ``pic-cli``.

Endpoints
---------
POST /verify
    Body: {"tool_name": "<name>", "tool_args": {"__pic": {…}, …}}
    200:  {"allowed": true,  "error": null,          "eval_ms": <int>}
    200:  {"allowed": false, "error": {"code": "…", "message": "…"}, "eval_ms": <int>}

GET  /health
    200:  {"status": "ok"}

Design notes
------------
* stdlib only – no Flask / FastAPI dependency.
* Fail-closed – any internal error returns ``allowed: false``.
* Binds to 127.0.0.1 by default (localhost-only for security).
* Reuses the battle-tested ``evaluate_pic_for_tool_call`` pipeline
  (limits → schema → verifier → tool-binding → evidence → time-budget).
"""

from __future__ import annotations

import json
import logging
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional

from pic_standard.config import load_policy
from pic_standard.errors import PICError, PICErrorCode
from pic_standard.integrations.mcp_pic_guard import (
    PICEvaluateLimits,
    evaluate_pic_for_tool_call,
    _debug_enabled,
)
from pic_standard.policy import PICPolicy

log = logging.getLogger("pic_standard.http_bridge")

# Maximum request body size (1MB) to prevent memory exhaustion attacks
MAX_REQUEST_BYTES = 1024 * 1024

# Socket read timeout (seconds) to prevent slow/malicious clients from hanging the server
READ_TIMEOUT_SECS = 5.0

# ------------------------------------------------------------------
# Request / response helpers
# ------------------------------------------------------------------

def _json_response(handler: BaseHTTPRequestHandler, status: int, body: Dict[str, Any]) -> None:
    """Write a JSON response with proper headers."""
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _read_json_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    """Read and parse JSON request body. Raises ValueError on bad input."""
    content_type = handler.headers.get("Content-Type", "")
    if content_type and "application/json" not in content_type:
        raise ValueError(f"Expected Content-Type application/json, got '{content_type}'")

    length_str = handler.headers.get("Content-Length")
    if not length_str:
        raise ValueError("Missing Content-Length header")

    try:
        length = int(length_str)
    except ValueError:
        log.warning("Malformed Content-Length header: %r", length_str)
        raise ValueError(f"Invalid Content-Length header: '{length_str}'")

    if length < 0:
        log.warning("Negative Content-Length received: %d", length)
        raise ValueError(f"Invalid Content-Length: negative value ({length})")
    if length == 0:
        raise ValueError("Empty request body")
    if length > MAX_REQUEST_BYTES:
        log.warning("Oversized request body: %d bytes (max %d)", length, MAX_REQUEST_BYTES)
        raise ValueError(f"Request body too large: {length} bytes (max {MAX_REQUEST_BYTES})")

    # Set socket timeout to prevent hanging on slow/malicious clients
    # that send fewer bytes than Content-Length claims
    original_timeout = handler.connection.gettimeout()
    try:
        handler.connection.settimeout(READ_TIMEOUT_SECS)
        raw = handler.rfile.read(length)
    finally:
        handler.connection.settimeout(original_timeout)

    if len(raw) < length:
        log.warning("Incomplete request body: expected %d bytes, got %d", length, len(raw))
        raise ValueError(f"Incomplete request body: expected {length} bytes, got {len(raw)}")

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Request body must be a JSON object (dict), got {type(data).__name__}")
    return data


# ------------------------------------------------------------------
# Core verification (thin wrapper around evaluate_pic_for_tool_call)
# ------------------------------------------------------------------

def handle_verify(
    body: Dict[str, Any],
    *,
    policy: PICPolicy,
    limits: PICEvaluateLimits,
    verify_evidence: bool,
    proposal_base_dir: Path,
    evidence_root_dir: Optional[Path],
) -> Dict[str, Any]:
    """
    Run PIC verification and return a structured response dict.

    Always returns – never raises.
    """
    t0 = time.perf_counter()

    tool_name = body.get("tool_name")
    tool_args = body.get("tool_args")

    if not isinstance(tool_name, str) or not tool_name.strip():
        return {
            "allowed": False,
            "error": {"code": "PIC_INVALID_REQUEST", "message": "Missing or empty 'tool_name'"},
            "eval_ms": int((time.perf_counter() - t0) * 1000),
        }

    if not isinstance(tool_args, dict):
        return {
            "allowed": False,
            "error": {"code": "PIC_INVALID_REQUEST", "message": "'tool_args' must be an object"},
            "eval_ms": int((time.perf_counter() - t0) * 1000),
        }

    try:
        evaluate_pic_for_tool_call(
            tool_name=tool_name.strip(),
            tool_args=tool_args,
            policy=policy,
            limits=limits,
            verify_evidence=verify_evidence,
            proposal_base_dir=proposal_base_dir,
            evidence_root_dir=evidence_root_dir,
        )
        eval_ms = int((time.perf_counter() - t0) * 1000)
        log.info("ALLOW tool=%s eval_ms=%d", tool_name.strip(), eval_ms)
        return {
            "allowed": True,
            "error": None,
            "eval_ms": eval_ms,
        }

    except PICError as e:
        eval_ms = int((time.perf_counter() - t0) * 1000)
        log.info("BLOCK tool=%s code=%s eval_ms=%d", tool_name.strip(), e.code.value, eval_ms)
        result: Dict[str, Any] = {
            "allowed": False,
            "error": {"code": e.code.value, "message": e.message},
            "eval_ms": eval_ms,
        }
        if _debug_enabled() and e.details:
            result["error"]["details"] = e.details
        return result

    except Exception as e:
        eval_ms = int((time.perf_counter() - t0) * 1000)
        log.exception("BLOCK tool=%s reason=internal_error eval_ms=%d", tool_name.strip(), eval_ms)
        result = {
            "allowed": False,
            "error": {"code": PICErrorCode.INTERNAL_ERROR.value, "message": "Internal verification error"},
            "eval_ms": eval_ms,
        }
        if _debug_enabled():
            result["error"]["details"] = {
                "exception_type": type(e).__name__,
                "exception": str(e),
            }
        return result


# ------------------------------------------------------------------
# HTTP handler
# ------------------------------------------------------------------

def _method_not_allowed(handler: BaseHTTPRequestHandler) -> None:
    _json_response(handler, 405, {"error": "Method not allowed"})


class PICBridgeHandler(BaseHTTPRequestHandler):
    """
    Minimal HTTP handler for PIC verification.

    Server-level config is stored on the *server* instance (see ``start_bridge``).
    """

    # Suppress default stderr logging per request (we use our own logger)
    def log_message(self, fmt: str, *args: Any) -> None:  # type: ignore[override]
        log.debug(fmt, *args)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            _json_response(self, 200, {"status": "ok"})
            return
        _json_response(self, 404, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/verify":
            _json_response(self, 404, {"error": "Not found"})
            return

        try:
            body = _read_json_body(self)
        except ValueError as e:
            # Specific validation errors (missing header, too large, etc.)
            _json_response(self, 400, {
                "allowed": False,
                "error": {"code": "PIC_INVALID_REQUEST", "message": str(e)},
                "eval_ms": 0,
            })
            return
        except Exception:
            # JSON parse errors or unexpected issues
            _json_response(self, 400, {
                "allowed": False,
                "error": {"code": "PIC_INVALID_REQUEST", "message": "Malformed or non-JSON body"},
                "eval_ms": 0,
            })
            return

        srv: PICBridgeServer = self.server  # type: ignore[assignment]
        result = handle_verify(
            body,
            policy=srv.policy,
            limits=srv.limits,
            verify_evidence=srv.verify_evidence,
            proposal_base_dir=srv.proposal_base_dir,
            evidence_root_dir=srv.evidence_root_dir,
        )
        _json_response(self, 200, result)

    # Unsupported methods → 405
    do_PUT = _method_not_allowed
    do_DELETE = _method_not_allowed
    do_PATCH = _method_not_allowed


# ------------------------------------------------------------------
# Server with config
# ------------------------------------------------------------------

class PICBridgeServer(HTTPServer):
    """HTTPServer subclass that holds PIC configuration."""

    def __init__(
        self,
        server_address: tuple,
        *,
        policy: PICPolicy,
        limits: Optional[PICEvaluateLimits] = None,
        verify_evidence: bool = False,
        proposal_base_dir: Optional[Path] = None,
        evidence_root_dir: Optional[Path] = None,
    ) -> None:
        super().__init__(server_address, PICBridgeHandler)
        self.policy = policy
        self.limits = limits or PICEvaluateLimits()
        self.verify_evidence = verify_evidence
        self.proposal_base_dir = proposal_base_dir or Path(".").resolve()
        self.evidence_root_dir = evidence_root_dir


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def start_bridge(
    *,
    host: str = "127.0.0.1",
    port: int = 7580,
    policy: Optional[PICPolicy] = None,
    limits: Optional[PICEvaluateLimits] = None,
    verify_evidence: bool = False,
    proposal_base_dir: Optional[Path] = None,
    evidence_root_dir: Optional[Path] = None,
) -> None:
    """
    Start the PIC HTTP bridge server (blocking).

    Parameters
    ----------
    host : str
        Bind address.  Defaults to ``127.0.0.1`` (localhost-only).
    port : int
        Listen port.  Defaults to ``7580``.
    policy : PICPolicy | None
        Tool-impact policy.  When ``None``, loaded via ``load_policy()``.

    Notes
    -----
    This server is single-threaded and processes one request at a time.
    For production deployments with concurrent load, run multiple bridge
    instances behind a load balancer or use a process manager.

    A 5-second socket read timeout (READ_TIMEOUT_SECS) prevents slow clients
    from blocking the server indefinitely during request body reading.
    """
    policy = policy or load_policy()

    server = PICBridgeServer(
        (host, port),
        policy=policy,
        limits=limits,
        verify_evidence=verify_evidence,
        proposal_base_dir=proposal_base_dir,
        evidence_root_dir=evidence_root_dir,
    )

    log.info("PIC HTTP bridge listening on %s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("PIC HTTP bridge shutting down")
    finally:
        server.server_close()
