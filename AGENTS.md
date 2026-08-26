# Documentation project instructions

## About this project

- API documentation for [Origami](https://origami.chat), an AI-powered lead generation and data enrichment platform
- Built on [Mintlify](https://mintlify.com)
- Pages are MDX files with YAML frontmatter
- Configuration lives in `docs.json`
- API reference is auto-generated from `openapi-v3.yaml` (current), `openapi-v2.yaml`, and `openapi-v1.yaml`
- `openapi-v3.yaml` is generated upstream in paper-crane. Do not hand-edit it — regenerate there, then run `python3 scripts/adjust-openapi-v3.py`
- That script owns the plain-English page and sidebar titles for every v3 endpoint (the `TITLES` table). A new upstream operation prints a warning until you add one
- Webhook events are auto-generated from `openapi-webhooks.yaml` (sequencer + tables) and `openapi-webhooks-jobs.yaml` (v3 Job events)
- Run `mint dev` to preview locally

## Terminology

- Use "Origami" (not "Origami AI" or "the platform")
- Use "list" for the v3 API resource (the product UI and v1/v2 still say "table")
- Use "table" in v1/v2 docs (not "spreadsheet" or "sheet")
- Use "enrichment" (not "data lookup" or "data pull")
- Use "row" (not "record" or "entry")
- Use "column" (not "field" — except when referring to JSON request fields)
- Use "API key" (not "token" or "secret key")
- Use "job" for v3 async work; "batch" only in v1/v2 docs
- Use "credits" for the billing unit

## Style preferences

- Use active voice and second person ("you")
- Keep sentences concise — one idea per sentence
- Use sentence case for headings
- Bold for UI elements: Click **Settings**
- Code formatting for file names, commands, paths, API endpoints, and field names
- Show curl examples for all endpoints
- Always show both request and response in code examples

## Content boundaries

- Document the public API: v3 (current), v2, and v1 (both deprecated for new integrations)
- Do not expose internal implementation details, database schemas, or worker architecture
- Do not reference internal tools, admin endpoints, or unreleased features
- Keep examples realistic but use fictional company data
