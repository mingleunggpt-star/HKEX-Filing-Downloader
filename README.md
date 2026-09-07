# HKEX Downloader v3.4 — Vercel Blob OIDC patch

Replace only:
- `api/_hkex_engine.py`
- `requirements.txt`

Do **not** add `BLOB_READ_WRITE_TOKEN`.

The connected Vercel Blob store should supply `BLOB_STORE_ID` and a short-lived `VERCEL_OIDC_TOKEN` automatically. The Vercel Python SDK then authenticates Blob uploads through OIDC.

After redeploying:
1. `/api/health` should still work.
2. Open `/`.
3. Test `0066`.
4. If it fails, check Runtime Logs and capture the final traceback lines.
