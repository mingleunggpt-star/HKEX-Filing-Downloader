# HKEX Downloader v3.5 — Direct OIDC Blob Upload

Replace:
- `api/index.py`
- `api/_hkex_engine.py`
- `requirements.txt`

This version does **not** use the Python Vercel Blob SDK.

Instead:
- FastAPI reads Vercel's per-request `x-vercel-oidc-token` header.
- `_hkex_engine.py` calls the Vercel Blob HTTP API directly with that Bearer token.
- `BLOB_STORE_ID` comes from the connected Blob store.

No `BLOB_READ_WRITE_TOKEN` is required.

Test order:
1. `/api/health` should show version 3.5
2. `/` should show the UI
3. Run `0066`
