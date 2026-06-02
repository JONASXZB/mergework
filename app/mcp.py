from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.bounty_availability import BOUNTY_AVAILABILITY_FILTERS
from app.bounty_sorting import BOUNTY_SORT_OPTIONS
from app.ledger.service import LedgerError

MCPToolHandler = Callable[[str, str, dict[str, Any]], str | dict[str, Any]]

POSITIVE_INTEGER_INPUT_SCHEMA = {
    "anyOf": [
        {"type": "integer", "minimum": 1},
        {
            "type": "string",
            "pattern": "^[1-9][0-9]*$",
            "description": "Positive integer value encoded as a string.",
        },
    ],
}

LOWERCASE_HEX_64_INPUT_SCHEMA = {
    "type": "string",
    "minLength": 64,
    "maxLength": 64,
    "pattern": "^[0-9a-f]{64}$",
}

LOWERCASE_HEX_128_INPUT_SCHEMA = {
    "type": "string",
    "minLength": 128,
    "maxLength": 128,
    "pattern": "^[0-9a-f]{128}$",
}


def _mcp_input_schema(
    properties: dict[str, Any], *, required: list[str] | None = None
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


MCP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_bounties",
        "description": (
            "List MRWK bounties with optional status, q, sort, limit, and availability filters"
        ),
        "inputSchema": _mcp_input_schema(
            {
                "status": {
                    "type": "string",
                    "enum": ["open", "paid", "closed"],
                    "default": "open",
                    "description": "Bounty status filter.",
                },
                "q": {
                    "type": "string",
                    "description": "Optional text or issue-number search query.",
                },
                "sort": {
                    "type": "string",
                    "enum": list(BOUNTY_SORT_OPTIONS),
                    "default": "newest",
                    "description": "Sort order for returned bounties.",
                },
                "limit": {
                    **POSITIVE_INTEGER_INPUT_SCHEMA,
                    "default": 25,
                    "description": "Maximum number of bounties to return, from 1 to 100.",
                },
                "availability": {
                    "type": "string",
                    "enum": sorted(BOUNTY_AVAILABILITY_FILTERS),
                    "default": "all",
                    "description": "Effective availability filter.",
                },
            },
        ),
    },
    {
        "name": "get_bounty",
        "description": "Get a bounty by id, optionally with accepted awards",
        "inputSchema": _mcp_input_schema(
            {
                "id": {
                    **POSITIVE_INTEGER_INPUT_SCHEMA,
                    "description": "Internal MRWK bounty id.",
                },
                "include_awards": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include accepted award proof rows.",
                },
            },
            required=["id"],
        ),
    },
    {
        "name": "list_bounty_attempts",
        "description": "List advisory active-attempt reservations for a bounty",
        "inputSchema": _mcp_input_schema(
            {
                "bounty_id": {
                    **POSITIVE_INTEGER_INPUT_SCHEMA,
                    "description": "Internal MRWK bounty id.",
                },
                "include_expired": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include expired attempt reservations.",
                },
                "limit": {
                    **POSITIVE_INTEGER_INPUT_SCHEMA,
                    "default": 25,
                    "description": "Maximum number of attempts to return, from 1 to 100.",
                },
            },
            required=["bounty_id"],
        ),
    },
    {
        "name": "get_balance",
        "description": "Get an account balance",
        "inputSchema": _mcp_input_schema(
            {
                "account": {
                    "type": "string",
                    "description": (
                        "MRWK ledger account such as treasury:mrwk, github:<login>, or mrwk1..."
                    ),
                },
            },
            required=["account"],
        ),
    },
    {
        "name": "register_wallet",
        "description": "Register an MRWK wallet public key",
        "inputSchema": _mcp_input_schema(
            {
                "public_key_hex": {
                    **LOWERCASE_HEX_64_INPUT_SCHEMA,
                    "description": "64-character lowercase hex Ed25519 public key.",
                },
                "label": {
                    "type": "string",
                    "description": "Optional wallet display label.",
                },
            },
            required=["public_key_hex"],
        ),
    },
    {
        "name": "get_wallet",
        "description": "Get an MRWK wallet by address",
        "inputSchema": _mcp_input_schema(
            {
                "address": {
                    "type": "string",
                    "description": "Registered mrwk1 wallet address.",
                },
            },
            required=["address"],
        ),
    },
    {
        "name": "submit_wallet_transfer",
        "description": "Submit a signed MRWK wallet transfer",
        "inputSchema": _mcp_input_schema(
            {
                "from_address": {
                    "type": "string",
                    "description": "Sender registered mrwk1 wallet address.",
                },
                "to_address": {
                    "type": "string",
                    "description": "Receiver registered mrwk1 wallet address.",
                },
                "amount_mrwk": {
                    "type": "string",
                    "description": "Decimal MRWK amount to transfer.",
                },
                "nonce": {
                    **POSITIVE_INTEGER_INPUT_SCHEMA,
                    "description": "Wallet transfer nonce.",
                },
                "memo": {
                    "type": "string",
                    "description": "Optional transfer memo.",
                },
                "signature_hex": {
                    **LOWERCASE_HEX_128_INPUT_SCHEMA,
                    "description": "128-character lowercase hex Ed25519 signature.",
                },
            },
            required=["from_address", "to_address", "amount_mrwk", "nonce", "signature_hex"],
        ),
    },
    {
        "name": "get_ledger_entry",
        "description": "Get a ledger entry",
        "inputSchema": _mcp_input_schema(
            {
                "sequence": {
                    **POSITIVE_INTEGER_INPUT_SCHEMA,
                    "description": "MRWK ledger sequence number.",
                },
            },
            required=["sequence"],
        ),
    },
    {
        "name": "get_proof",
        "description": "Get a public proof by hash",
        "inputSchema": _mcp_input_schema(
            {
                "hash": {
                    **LOWERCASE_HEX_64_INPUT_SCHEMA,
                    "description": "64-character lowercase hex public proof hash.",
                },
            },
            required=["hash"],
        ),
    },
    {
        "name": "submit_work_proof",
        "description": (
            "Return submission instructions for bounty_id or issue_number, optionally "
            "scoping issue_number by repo, with text or json format"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "bounty_id": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Internal MRWK bounty id. Use either bounty_id or issue_number.",
                },
                "issue_number": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "GitHub issue number for an MRWK bounty. "
                        "Use either issue_number or bounty_id."
                    ),
                },
                "repo": {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Optional owner/name repository scope for issue_number lookups.",
                },
                "format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "default": "text",
                    "description": "Use json for machine-readable structuredContent guidance.",
                },
            },
            "additionalProperties": False,
            "not": {"required": ["bounty_id", "issue_number"]},
        },
    },
]


def _jsonrpc_error(response_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": response_id, "error": {"code": code, "message": message}}


def _tool_result_response(response_id: Any, tool_result: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(tool_result, dict):
        return {
            "jsonrpc": "2.0",
            "id": response_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(tool_result)}],
                "structuredContent": tool_result,
            },
        }
    return {
        "jsonrpc": "2.0",
        "id": response_id,
        "result": {"content": [{"type": "text", "text": tool_result}]},
    }


async def handle_mcp_request(
    request: Request, database_url: str, call_tool: MCPToolHandler
) -> dict[str, Any] | JSONResponse:
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(_jsonrpc_error(None, -32700, "parse error"), status_code=400)

    if not isinstance(payload, dict):
        return JSONResponse(_jsonrpc_error(None, -32600, "invalid request"), status_code=400)

    response_id = payload.get("id")
    method = payload.get("method")
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": response_id, "result": {"tools": MCP_TOOLS}}

    if method != "tools/call":
        return _jsonrpc_error(response_id, -32601, "unknown method")

    params = payload.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return _jsonrpc_error(response_id, -32602, "invalid params")

    name = params.get("name")
    args = params.get("arguments", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return _jsonrpc_error(response_id, -32602, "invalid params")
    if not isinstance(name, str):
        return _jsonrpc_error(response_id, -32602, "tool name is required")

    try:
        tool_result = call_tool(database_url, name, args)
    except (KeyError, TypeError, ValueError, LedgerError, HTTPException):
        return _jsonrpc_error(response_id, -32602, "invalid tool arguments")

    return _tool_result_response(response_id, tool_result)
