# Deploy Mintlify docs at origami.chat/docs

## Goal

Serve the Mintlify documentation site at `origami.chat/docs` so it looks like part of the main site, while the main app continues running on Render.

## Architecture

```
Browser → origami.chat/docs/* → Cloudflare Worker (proxy) → origamiagents.mintlify.dev/docs/*
Browser → origami.chat/*      → Render (main app, unchanged)
```

The Cloudflare Worker acts as a reverse proxy — it fetches content from Mintlify and returns it to the browser without the URL ever changing. This is NOT a redirect; the user always sees `origami.chat/docs` in their address bar.

## Why Cloudflare Worker (not Vercel rewrites)

- The main app is hosted on **Render**, not Vercel, so Vercel rewrites aren't an option.
- Render doesn't support URL rewrites/proxying to external origins.
- `origami.chat` already uses Cloudflare for DNS (nameservers: `adel.ns.cloudflare.com`, `sergi.ns.cloudflare.com`), so a Worker is the natural fit.
- Using a Worker **Route** (not Custom Domain) means only `/docs*` traffic is intercepted — everything else flows to Render untouched. Zero risk to the main app.

## Steps

### 1. Mintlify dashboard — DONE

- Navigated to [Custom domain setup](https://dashboard.mintlify.com/settings/deployment/custom-domain)
- Toggled on "Host at `/docs`"
- Entered `origami.chat` and clicked **Add domain**
- This tells Mintlify's servers to accept requests from `origami.chat/docs`

### 2. Create Cloudflare Worker

1. Go to [Cloudflare dashboard](https://dash.cloudflare.com/) → **Workers & Pages** → **Create** → **Create Worker**
2. Name it `origami-docs-proxy` (or whatever you like)
3. Click **Deploy** (deploys with default Hello World code)
4. Click **Edit Code** and replace everything with:

```javascript
addEventListener("fetch", (event) => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  try {
    const urlObject = new URL(request.url);

    if (/^\/docs/.test(urlObject.pathname)) {
      const DOCS_URL = "origamiagents.mintlify.dev";
      const CUSTOM_URL = "origami.chat";

      let url = new URL(request.url);
      url.hostname = DOCS_URL;

      let proxyRequest = new Request(url, request);
      proxyRequest.headers.set("Host", DOCS_URL);
      proxyRequest.headers.set("X-Forwarded-Host", CUSTOM_URL);
      proxyRequest.headers.set("X-Forwarded-Proto", "https");

      return await fetch(proxyRequest);
    }

    return await fetch(request);
  } catch (error) {
    return await fetch(request);
  }
}
```

5. Click **Deploy**

> **Note:** Replace `origamiagents` if your Mintlify subdomain is different. Check your Mintlify dashboard URL: `dashboard.mintlify.com/<org>/<subdomain>` — use the `<subdomain>` part.

### 3. Test the Worker

Hit the Worker's preview URL: `origami-docs-proxy.<your-cf-account>.workers.dev/docs`

You should see your Mintlify docs rendered. If you get a blank page or error, double-check the subdomain value.

### 4. Add a Worker Route

**Use a Route, NOT a Custom Domain.** A Custom Domain takes over ALL traffic for `origami.chat` which could break the Render app.

1. In the Worker settings → **Settings** → **Domains & Routes** → **Add**
2. Choose **Route**
3. Route pattern: `origami.chat/docs*`
4. Zone: `origami.chat`
5. Save

This ensures only `/docs` and `/docs/anything` go through the Worker. All other paths continue to Render.

### 5. Cloudflare SSL settings

- Go to **SSL/TLS** in Cloudflare dashboard for `origami.chat`
- Encryption mode should be **Full (strict)**
- Under **Edge Certificates**, disable **"Always Use HTTPS"** (can interfere with Let's Encrypt cert provisioning for Mintlify)

### 6. Update docs.json for SEO

Add a canonical URL to `docs.json` in the mintlify-docs repo so search engines index the right domain:

```json
"seo": {
  "metatags": {
    "canonical": "https://origami.chat/docs"
  }
}
```

### 7. Verify

- Visit `origami.chat/docs` — should show the Mintlify docs
- Visit `origami.chat` — should show the main app (Render), unaffected
- Visit `origami.chat/docs/quickstart` — should show the quickstart page
- Visit `app.origami.chat` — should be unaffected

## Troubleshooting

- **`origami.chat/docs` returns 404 or shows the main app:** The Worker Route isn't active yet. Check that the route pattern is exactly `origami.chat/docs*` and the zone is correct. DNS propagation can take a few minutes.
- **Docs load but assets (CSS/JS) are broken:** Make sure the route pattern catches all subpaths (`docs*` not just `docs`). Mintlify assets are served from `/_mintlify/` — if those aren't proxied, you may need to add another route: `origami.chat/_mintlify*`.
- **SSL errors:** Ensure Cloudflare SSL is set to Full (strict) and "Always Use HTTPS" is off.
- **Main app broken:** This should NOT happen with a Route. If it does, delete the Worker Route immediately — the main app will recover instantly since DNS still points to Render.
