#!/usr/bin/env python3
"""Adjust paper-crane's generated openapi-v3.yaml for Mintlify.

Three jobs:

1. The catalog emits Express-style `{id}` path templates while the path
   parameter is named `job_id` / `list_id` / `campaign_id` / …. Mintlify
   requires the template name to match the parameter name.
2. Every operation gets an `x-mint` block: a stable `href` so guide pages
   can link `/v3/reference/<operation-id>`, plus `metadata` that gives the
   generated page a plain-English title and a subtitle. Catalog summaries
   that contain `:` or `{ k: v }` are rewritten — Mintlify copies the
   description into unquoted MDX frontmatter, and those characters crash
   the preview. Without `x-mint` the sidebar reads as a list of catalog
   identifiers instead of a list of things you can do.
3. Rewrites `/jobs/{id}` mentions in prose and prepends a Mintlify
   adjustment note to the file header.

The script is idempotent — it strips any `x-mint` block it previously
wrote before injecting a fresh one, so re-running after a regenerate is
always safe.
"""

from __future__ import annotations

import json
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

# Plain-English page titles, keyed by operationId. The catalog's own
# `summary` stays on the operation (generators and the API playground use
# it) and is surfaced as the page description; this is what a reader sees
# in the sidebar and as the page heading. Keep entries short and concrete
# — "Enroll people", not "send.campaigns.people.upsert".
TITLES = {
    # ── Jobs ──────────────────────────────────────────────────────────────
    "jobs.list": "List jobs",
    "jobs.get": "Get a job",
    "jobs.cancel": "Cancel a job",
    "jobs.input": "Answer a job's questions",

    # ── Account: org ──────────────────────────────────────────────────────
    "account.get": "Get your account",
    "account.credits.get": "Credit balance",
    "account.credits.usage": "Credit usage",
    "account.rate_limits.get": "Rate limits",

    # ── Account: projects ─────────────────────────────────────────────────
    "account.projects.list": "List projects",
    "account.projects.create": "Create a project",
    "account.projects.get": "Get a project",
    "account.projects.patch": "Update a project",
    "account.projects.delete": "Delete a project",

    # ── Account: chats ────────────────────────────────────────────────────
    "account.chats.list": "List chats",
    "account.chats.create": "Create a chat",
    "account.chats.get": "Get a chat",
    "account.chats.patch": "Rename a chat",
    "account.chats.archive": "Archive a chat",
    "account.chats.links.create": "Link a list or campaign",
    "account.chats.links.delete": "Unlink a list or campaign",
    "account.chats.messages.create": "Send a chat message",

    # ── Account: senders ──────────────────────────────────────────────────
    "account.senders.list": "List senders",
    "account.senders.get": "Get a sender",
    "account.senders.patch": "Update a sender",
    "account.senders.delete": "Disconnect a sender",
    "account.senders.warmup.enable": "Turn warmup on",
    "account.senders.warmup.disable": "Turn warmup off",
    "account.senders.imap.create": "Connect an SMTP/IMAP mailbox",
    "account.senders.connect": "Connect via OAuth",
    "account.senders.reconnect": "Reconnect a sender",
    "account.senders.send_as_aliases.list": "List send-as aliases",

    # ── Account: domains & mailboxes ──────────────────────────────────────
    "account.domains.search": "Search for domains",
    "account.domains.list": "List your domains",
    "account.domains.get": "Get a domain",
    "account.domains.purchase": "Buy domains",
    "account.domains.renewal.cancel": "Turn off auto-renewal",
    "account.domains.renewal.undo": "Turn auto-renewal back on",
    "account.domains.forwarding.set": "Set domain forwarding",
    "account.mailboxes.list": "List mailboxes",
    "account.mailboxes.provision": "Create mailboxes",

    # ── Account: exclusion lists ──────────────────────────────────────────
    "account.exclusion_lists.get": "Get exclusion settings",
    "account.exclusion_lists.patch": "Switch exclusion source",
    "account.exclusion_lists.people.list": "List excluded people",
    "account.exclusion_lists.people.add": "Exclude people",
    "account.exclusion_lists.people.clear": "Clear excluded people",
    "account.exclusion_lists.people.delete": "Un-exclude one person",
    "account.exclusion_lists.companies.list": "List excluded companies",
    "account.exclusion_lists.companies.add": "Exclude companies",
    "account.exclusion_lists.companies.clear": "Clear excluded companies",
    "account.exclusion_lists.companies.delete": "Un-exclude one company",

    # ── Account: webhooks ─────────────────────────────────────────────────
    "account.webhooks.list": "List endpoints",
    "account.webhooks.create": "Create an endpoint",
    "account.webhooks.get": "Get an endpoint",
    "account.webhooks.patch": "Update an endpoint",
    "account.webhooks.delete": "Delete an endpoint",
    "account.webhooks.rotate": "Rotate the signing secret",
    "account.webhooks.test": "Send a test event",

    # ── Account: API keys ─────────────────────────────────────────────────
    "account.keys.list": "List API keys",
    "account.keys.create": "Create an API key",
    "account.keys.revoke": "Revoke an API key",

    # ── Leads: lists ──────────────────────────────────────────────────────
    "leads.lists.list": "List your lists",
    "leads.lists.create": "Create an empty list",
    "leads.lists.get": "Get a list",
    "leads.lists.patch": "Rename a list",
    "leads.lists.delete": "Delete a list",
    "leads.lists.stats.get": "List stats",
    "leads.lists.fetch": "Find leads for a list",
    "leads.lists.fetch_more": "Find more leads",
    "leads.lists.enrich": "Enrich existing columns",
    "leads.lists.enrich_custom": "Enrich from instructions",

    # ── Leads: columns ────────────────────────────────────────────────────
    "leads.lists.columns.create": "Add a column",
    "leads.lists.columns.copy": "Copy a column",
    "leads.lists.columns.patch": "Update a column",
    "leads.lists.columns.delete": "Delete a column",

    # ── Leads: rows ───────────────────────────────────────────────────────
    "leads.lists.rows.list": "Read rows",
    "leads.lists.rows.get": "Read one row",
    "leads.lists.rows.upsert": "Add or update rows",
    "leads.lists.rows.delete": "Delete rows",
    "leads.lists.rows.cells.get": "Read one cell",

    # ── Leads: searches ───────────────────────────────────────────────────
    "leads.searches.create": "Search for leads",
    "leads.searches.get": "Get a search",
    "leads.searches.fetch_more": "Fetch more results",

    # ── Send: campaigns ───────────────────────────────────────────────────
    "send.campaigns.list": "List campaigns",
    "send.campaigns.create": "Create a campaign",
    "send.campaigns.get": "Get a campaign",
    "send.campaigns.delete": "Delete a campaign",
    "send.campaigns.stats.get": "Campaign stats",
    "send.campaigns.draft": "Draft from a brief",
    "send.campaigns.launch": "Launch a campaign",
    "send.campaigns.pause": "Pause a campaign",
    "send.campaigns.resume": "Resume a campaign",
    "send.campaigns.settings.get": "Get settings",
    "send.campaigns.settings.patch": "Update settings",
    "send.campaigns.senders.list": "List campaign senders",
    "send.campaigns.senders.add": "Add a sender",
    "send.campaigns.senders.remove": "Remove a sender",

    # ── Send: people ──────────────────────────────────────────────────────
    "send.campaigns.people.schema.get": "Get the person fields",
    "send.campaigns.people.schema.put": "Set the person fields",
    "send.campaigns.people.list": "List enrolled people",
    "send.campaigns.people.upsert": "Enroll people",
    "send.campaigns.people.get": "Get one person",
    "send.campaigns.people.delete": "Delete a person",
    "send.campaigns.people.contact.patch": "Update contact details",
    "send.campaigns.people.steps.patch": "Edit one message",
    "send.campaigns.people.remove": "Cancel a sequence",
    "send.campaigns.people.stop": "Stop a sequence",
    "send.campaigns.people.remove_bulk": "Cancel sequences in bulk",
    "send.campaigns.people.revert": "Undo edits to a person",
    "send.campaigns.people.sender.pin": "Pin a sender to a person",
    "send.campaigns.people.sender.unpin": "Unpin a person's sender",

    # ── Send: templates ───────────────────────────────────────────────────
    "send.campaigns.templates.get": "Get the template",
    "send.campaigns.templates.put": "Replace the template",
    "send.campaigns.templates.clear": "Clear the template",
    "send.campaigns.templates.sequences.append": "Add a variant",
    "send.campaigns.templates.sequences.patch": "Update a variant",
    "send.campaigns.templates.sequences.delete": "Delete a variant",

    # ── Send: previews & approvals ────────────────────────────────────────
    "send.campaigns.examples.list": "Read generated messages",
    "send.campaigns.examples.generate": "Generate messages",
    "send.campaigns.approvals.list": "List messages awaiting approval",
    "send.campaigns.approvals.approve": "Approve messages",
}


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


def strip_x_mint(text: str) -> str:
    """Remove x-mint blocks we wrote previously so injection is idempotent."""
    out: list[str] = []
    skipping = False
    for line in text.splitlines(keepends=True):
        if skipping:
            # The block ends at the first line indented less than its children.
            if line.startswith(" " * 8) or not line.strip():
                continue
            skipping = False
        if re.match(r"^      x-mint:\n$", line):
            skipping = True
            continue
        out.append(line)
    return "".join(out)


def collect_summaries(doc: dict) -> dict[str, str]:
    """operationId -> summary, read from the parsed doc.

    Summaries can be folded across lines in the YAML, so they are taken
    from the parsed document rather than scraped off the text.
    """
    summaries: dict[str, str] = {}
    for methods in doc["paths"].values():
        for op in methods.values():
            if isinstance(op, dict) and op.get("operationId"):
                summaries[op["operationId"]] = op.get("summary", "")
    return summaries


def is_yaml_plain_safe(s: str) -> bool:
    """True if `s` round-trips as an unquoted YAML plain scalar."""
    try:
        loaded = yaml.safe_load("description: " + s)
    except yaml.YAMLError:
        return False
    return isinstance(loaded, dict) and loaded.get("description") == s


# Catalog summaries that cannot be copied into unquoted MDX frontmatter as-is.
# Mintlify generates each endpoint page with `description: <summary>` and does
# not quote the value, so `key: value` and `{ k: v }` crash the preview.
SAFE_DESCRIPTIONS = {
    "jobs.get": "Read one job. Honor next_poll_at when you poll.",
    "account.get": "Read the org, including plan, capability flags, concurrent agent runs, and project counts.",
    "account.rate_limits.get": "Current rate-limit buckets, with limit, remaining, and reset per bucket.",
    "leads.lists.rows.upsert": "Upsert rows by match columns. Sync, and embeds an enrichment job when enrich is true.",
    "leads.searches.create": "One-shot search from a brief. Creates a list, runs the search, and returns the first page.",
    "send.campaigns.get": "Read one campaign, including schema, template, people, and settings.",
    "send.campaigns.draft": "Fill schema and templates from a brief. Never launches.",
    "send.campaigns.people.schema.put": "Replace the person schema. An empty fields list means identity-only.",
    "send.campaigns.people.get": "Read one person's sequence, including identity, per-step state, and sent copy.",
    "send.campaigns.templates.clear": "Clear the template to an empty sequences list.",
}


def mintlify_safe_frontmatter(s: str, operation_id: str = "") -> str:
    """Rewrite a catalog summary so Mintlify can put it in MDX frontmatter."""
    if operation_id in SAFE_DESCRIPTIONS:
        s = SAFE_DESCRIPTIONS[operation_id]
    if is_yaml_plain_safe(s):
        return s
    s = s.replace("{ fields: [] }", "an empty fields list")
    s = s.replace("{ sequences: [] }", "an empty sequences list")
    s = s.replace("enrich: true", "enrich is true")
    s = s.replace(": ", " — ")
    s = s.replace(":", " —")
    s = s.replace("{", "(").replace("}", ")")
    s = s.replace("[", "(").replace("]", ")")
    if not is_yaml_plain_safe(s):
        raise SystemExit(
            f"description is still unsafe as unquoted YAML: {s!r}"
        )
    print(f"warning: sanitized unmapped colon-bearing summary: {s!r}")
    return s


def inject_x_mint(text: str, summaries: dict[str, str]) -> str:
    """Give every operation a stable href and a readable title.

    `href` keeps guide links like `/v3/reference/leads-searches-create`
    working no matter how docs.json groups the endpoints. `metadata.title`
    sets the page heading and `metadata.sidebarTitle` the sidebar entry —
    both are needed, since the sidebar otherwise falls back to the
    operationId. `metadata.description` is a Mintlify-safe subtitle
    (catalog summaries with colons are rewritten — Mintlify does not
    quote them in generated MDX frontmatter).
    """
    out: list[str] = []
    unmapped: list[str] = []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(      )operationId: ([A-Za-z0-9_.]+)\n$", line)
        if m:
            indent, op = m.group(1), m.group(2)
            href = "/v3/reference/" + op.replace(".", "-").replace("_", "-")
            title = TITLES.get(op)
            if title is None:
                unmapped.append(op)
                # Fall back to the id minus its section, e.g. "rows upsert".
                title = op.split(".", 1)[-1].replace(".", " ").replace("_", " ")
                title = title[:1].upper() + title[1:]
            summary = summaries.get(op, "")
            description = (
                mintlify_safe_frontmatter(summary, op) if summary else ""
            )
            out.append(f"{indent}x-mint:\n")
            out.append(f"{indent}  href: {href}\n")
            out.append(f"{indent}  metadata:\n")
            out.append(f"{indent}    title: {json.dumps(title)}\n")
            # sidebarTitle is not optional here: without it Mintlify labels the
            # sidebar entry from the operationId ("Account senders imap create")
            # rather than from the page title.
            out.append(f"{indent}    sidebarTitle: {json.dumps(title)}\n")
            if description:
                out.append(f"{indent}    description: {json.dumps(description)}\n")
            out.append(line)
            i += 1
            # Only rewrite a following summary when the catalog string would
            # crash Mintlify's unquoted MDX frontmatter. Leave safe summaries
            # as paper-crane wrote them (including folded lines).
            if i < len(lines) and re.match(r"^      summary:", lines[i]):
                if summary and not is_yaml_plain_safe(summary):
                    out.append(f"{indent}summary: {json.dumps(description)}\n")
                    i += 1
                    while i < len(lines) and lines[i].startswith("        "):
                        i += 1
                    continue
            continue
        out.append(line)
        i += 1
    if unmapped:
        print(f"warning: no title mapped for {len(unmapped)} operations:")
        for op in unmapped:
            print(f"  - {op}")
        print("Add them to TITLES in this script.")
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
    drives HTTP (`https://origami.chat/api/v3`), the hosted MCP server
    (`https://origami.chat/mcp`), and the `origami` CLI.

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
    text = inject_x_mint(strip_x_mint(text), collect_summaries(doc))
    SPEC.write_text(text)

    adjusted = yaml.safe_load(text)
    leftover = [p for p in adjusted["paths"] if "{id}" in p]
    if leftover:
        raise SystemExit(f"Unrewritten {{id}} paths: {leftover}")
    unsafe = []
    for methods in adjusted["paths"].values():
        for op in methods.values():
            if not isinstance(op, dict):
                continue
            desc = (op.get("x-mint") or {}).get("metadata", {}).get(
                "description", ""
            )
            if desc and not is_yaml_plain_safe(desc):
                unsafe.append(op.get("operationId", "?"))
    if unsafe:
        raise SystemExit(
            "x-mint descriptions still unsafe as unquoted YAML: "
            + ", ".join(unsafe)
        )
    print(f"rewrote {len(renames)} paths in {SPEC}")
    print_nav(adjusted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
