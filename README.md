# HKEX Filing Downloader v4.1

Zero-config FastAPI deployment for Vercel.

## Repository structure

```text
HKEX-Filing-Downloader/
├── app.py
├── hkex_search.py
├── pyproject.toml
├── .gitignore
└── README.md
```

Delete the old deployment files/folders:

- `api/`
- `vercel.json`
- `requirements.txt`
- `index.html`
- all `*.pyc` and `__pycache__/`

Vercel supports root-level FastAPI `app.py`, so this version uses no rewrite configuration.

## Vercel settings

- Root Directory: `./`
- Build Command: Override OFF
- Output Directory: Override OFF
- Install Command: Override OFF
- Development Command: Override OFF

Let Vercel auto-detect FastAPI. If the Framework Preset is already `Other`, it can remain as long as the deployment detects `app.py` as FastAPI.

## Test order

1. `/api/health` -> version `4.1.0`
2. `/` -> Web UI
3. Search `0066`
4. Choose Downloads as the parent folder
5. App creates child folder `0066`
6. Test one PDF
7. Test multiple selected PDFs

## Download behavior

The Vercel backend only searches HKEX and returns a document list. The browser then tries to fetch each selected official HKEX PDF and write it to the local folder using the File System Access API.

If HKEX blocks browser cross-origin fetches (CORS), search/listing and `Open PDF` still work. A later version can add a single-file helper without returning to bulk ZIP processing.
