#!/usr/bin/env python3
"""Adjust paper-crane's generated openapi-v3.yaml for Mintlify.

The catalog emits Express-style `{id}` path templates while the path
parameter is named `job_id` / `list_id` / `campaign_id` / …. Mintlify
requires the template name to match the parameter name.

Also rewrites `/jobs/{id}` mentions in prose and prepends a Mintlify
adjustment note to the file header.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "openapi-v3.yaml"

HEADER_NOTE = (
    "# Copied from paper-crane and adjusted for Mintlify: path templates use\n"
    "# the field names (`{job_id}`, `{list_id}`, `{campaign_id}`, …) rather\n"
    "# than Express `:id`. Do not hand-merge back into paper-crane — regenerate\n"
    "# there, then re-run scripts/adjust-openapi-v3.py.\n"
)


def collect_renames(doc: dict) -> dict[str, str]:
    renames: dict[str, str] = {}
    for path, methods in doc["paths"].items():
        if "{id}" not in path:
            continue
        param_names: set[str] = set()
        for op in methods.values():
            if not isinstance(op, dict):
                continue
            for p in op.get("parameters") or []:
                if isinstance(p, dict) and p.get("in") == "path":
                    param_names.add(p["name"])
        candidates = [n for n in sorted(param_names) if "{" + n + "}" not in path]
        if len(candidates) != 1:
            raise SystemExit(
                f"Could not rewrite {path}: candidates={candidates} params={param_names}"
            )
        renames[path] = path.replace("{id}", "{" + candidates[0] + "}")
    return renames


def apply_renames(text: str, renames: dict[str, str]) -> str:
    # Longest first so `/foo/{id}/bar` is not partially matched by `/foo/{id}`.
    for old, new in sorted(renames.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"^  {re.escape(old)}:$", f"  {new}:", text, flags=re.M)
    text = text.replace("GET /jobs/{id}", "GET /jobs/{job_id}")
    text = text.replace("/jobs/{id}", "/jobs/{job_id}")
    return text


def prepend_header(text: str) -> str:
    if "adjusted for Mintlify" in text[:800]:
        return text
    # Keep the auto-generated banner, then add the Mintlify note.
    lines = text.splitlines(keepends=True)
    insert_at = 0
    while insert_at < len(lines) and lines[insert_at].startswith("#"):
        insert_at += 1
    lines.insert(insert_at, HEADER_NOTE)
    return "".join(lines)


def inject_x_mint(text: str) -> str:
    """Stable hrefs so guide pages can link `/v3/reference/<operation-id>`."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        m = re.match(r"^(      )operationId: ([A-Za-z0-9_.]+)\n$", line)
        if m:
            prev = "".join(out[-4:])
            if "x-mint:" not in prev:
                indent, op = m.group(1), m.group(2)
                href = "/v3/reference/" + op.replace(".", "-").replace("_", "-")
                out.append(f"{indent}x-mint:\n")
                out.append(f"{indent}  href: {href}\n")
        out.append(line)
    return "".join(out)


def expand_info_description(text: str) -> str:
    """Replace the one-paragraph info.description with Mintlify-oriented copy."""
    if "The Origami **v3 API** is the current public surface" in text:
        return text
    old = """  description: "The Origami v3 public API: three sections (Account, Leads, Send)
    plus the shared Jobs resource. One operation catalog drives HTTP, the hosted
    MCP server, and the origami CLI. Wire fields are snake_case; unknown request
    fields are rejected with 400 VALIDATION_ERROR. v1 and v2 remain available
    but deprecated for new integrations."
"""
    new = """  description: |
    The Origami **v3 API** is the current public surface: named, typed
    operations in three sections (**Account**, **Leads**, **Send**) plus
    one shared **Job** resource for all async work. The same catalog
    drives HTTP, the hosted MCP server, and the `origami` CLI.

    **Wire conventions.** Fields are `snake_case`. Every object carries
    an `object` type field. Every list is
    `{ "object": "list", "items": [...], "next_cursor": string|null, "url": string }`
    and pages with `cursor` + `limit` (max 100). Unknown request fields
    are rejected with `400 VALIDATION_ERROR` — a camelCase body fails
    loudly instead of being silently stripped.

    **Async work.** Async operations return `202` with a Job. Poll
    `GET /jobs/{job_id}` honoring `next_poll_at` / `Retry-After`, or
    subscribe to `job.*` webhooks. `succeeded` means the work
    *including enrichment* is done, so result counts are final.

    **Auth.** `Authorization: Bearer og_live_...`. Keys carry a role
    (`member` default, or `admin`). Scope a request to a child project
    with `x-origami-project: <project_id>`. The header applies to
    Leads, Send, Jobs, and — within Account — chats and exclusion
    lists. It is ignored by project management, org reads, senders,
    domains, mailboxes, webhooks, and API-key routes.

    **Idempotency.** Any POST may send `Idempotency-Key: <uuid>`. Reuse
    with a different body → `409 IDEMPOTENCY_MISMATCH`. A racing retry
    → `409 IDEMPOTENCY_PENDING` (honor `Retry-After`).

    v1 and v2 remain available but are deprecated for new integrations.
    See the v2 → v3 migration guide for the 1:1 flow map.
"""
    if old not in text:
        raise SystemExit("info.description block not found — spec format changed")
    return text.replace(old, new, 1)


def print_nav(doc: dict) -> None:
    print("# METHOD path")
    for path, methods in doc["paths"].items():
        for method in ("get", "post", "put", "patch", "delete"):
            if method in methods:
                print(f"{method.upper()} {path}")


def main() -> int:
    text = SPEC.read_text()
    doc = yaml.safe_load(text)
    renames = collect_renames(doc)
    text = apply_renames(text, renames)
    text = prepend_header(text)
    text = expand_info_description(text)
    text = inject_x_mint(text)
    SPEC.write_text(text)

    adjusted = yaml.safe_load(text)
    leftover = [p for p in adjusted["paths"] if "{id}" in p]
    if leftover:
        raise SystemExit(f"Unrewritten {{id}} paths: {leftover}")
    print(f"rewrote {len(renames)} paths in {SPEC}")
    print_nav(adjusted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
