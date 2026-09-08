# HKEX Filing Downloader v4.0.1 Clean

## IMPORTANT folder structure

Your GitHub repository root MUST look exactly like this:

```text
HKEX-Filing-Downloader/
├── api/
│   ├── __init__.py
│   ├── index.py
│   └── _hkex_search.py
├── .gitignore
├── requirements.txt
├── vercel.json
└── README.md
```

Do NOT move `index.py` or `_hkex_search.py` to the repository root.

Do NOT upload:
- `*.pyc`
- `__pycache__/`

## Vercel settings

Framework Preset: Other

Root Directory: ./

Build Command: Override OFF
Output Directory: Override OFF
Install Command: Override OFF
Development Command: Override OFF

## Test order

1. `/api/health` -> version 4.0
2. `/` -> web UI
3. search 0066
4. choose Downloads as the parent folder
5. create folder 0066
6. test downloading one PDF
