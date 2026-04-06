# Documentation project instructions

## About this project

- API documentation for [Origami](https://origami.chat), an AI-powered lead generation and data enrichment platform
- Built on [Mintlify](https://mintlify.com)
- Pages are MDX files with YAML frontmatter
- Configuration lives in `docs.json`
- API reference is auto-generated from `openapi-v1.yaml`
- Run `mint dev` to preview locally

## Terminology

- Use "Origami" (not "Origami AI" or "the platform")
- Use "table" (not "spreadsheet" or "sheet")
- Use "enrichment" (not "data lookup" or "data pull")
- Use "row" (not "record" or "entry")
- Use "column" (not "field" — except when referring to JSON request fields)
- Use "API key" (not "token" or "secret key")
- Use "batch" for async operation tracking units
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

- Only document the public API (v1 endpoints)
- Do not expose internal implementation details, database schemas, or worker architecture
- Do not reference internal tools, admin endpoints, or unreleased features
- Keep examples realistic but use fictional company data
