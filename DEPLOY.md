# Deploy V3

Delete old:
- app/
- package.json
- app.py
- old api/
- old vercel.json

Upload only V3 files.

Vercel settings:
- Root Directory: ./
- Build Command: empty/default
- Output Directory: empty/default
- Install Command: empty/default

Keep Blob store `hkex-filings` connected.

First test:
`https://YOUR-DOMAIN.vercel.app/api/health`

Expected:
`{"ok":true,"service":"hkex-filing-downloader","version":"3.0"}`

Then test `/`, then `0066`.
