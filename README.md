# HKEX Filing Downloader v4.2

## Architecture

- Vercel FastAPI: search HKEX and render the web UI.
- Cloudflare Worker: proxy one HKEX PDF at a time and add CORS headers.
- Browser File System Access API: save the PDF directly into your chosen local folder.

## Repository structure

```text
app.py
hkex_search.py
pyproject.toml
.gitignore
README.md

worker/
  worker.js
  wrangler.toml
```

## 1. Deploy the Cloudflare Worker

### Dashboard method

1. Log in to Cloudflare.
2. Open **Workers & Pages**.
3. Create a Worker.
4. Name it `hkex-pdf-proxy`.
5. Replace the default code with `worker/worker.js`.
6. Deploy it.
7. Copy the resulting URL, for example:

```text
https://hkex-pdf-proxy.<your-subdomain>.workers.dev
```

8. Test:

```text
https://YOUR-WORKER.workers.dev/health
```

Expected:

```json
{"ok":true,"service":"hkex-pdf-proxy","version":"1.0.0"}
```

### Wrangler method

```bash
npm install -g wrangler
wrangler login
cd worker
wrangler deploy
```

## 2. Put the Worker URL into app.py

Find:

```python
WORKER_BASE_URL = "https://REPLACE-ME.workers.dev"
```

Replace it with your real Worker URL.

Example:

```python
WORKER_BASE_URL = "https://hkex-pdf-proxy.example.workers.dev"
```

Commit and redeploy Vercel.

## 3. Test v4.2

1. `/api/health` should show version `4.2.0`.
2. Search `0066`.
3. Choose `Downloads` as the parent folder.
4. Keep folder name `0066`.
5. Select only one PDF first.
6. Download it.
7. Confirm it appears in `Downloads/0066/`.
8. Then test multiple PDFs.

## Security

The Worker is intentionally restricted. It accepts only:

- HTTPS URLs
- `www1.hkexnews.hk` / `www.hkexnews.hk`
- URL paths ending in `.pdf`

So it is not intended to be an open general-purpose proxy.

## Existing file handling

Default: **Skip**

Other options:
- Replace
- Rename
