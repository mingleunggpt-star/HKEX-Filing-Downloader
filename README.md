# HKEX Filing Downloader v4
V4 removes Vercel Blob and ZIP creation.

Flow:
1. Search stock on HKEX.
2. Show file list.
3. User chooses a parent folder (Chrome/Edge).
4. App creates a child folder using the requested name (default stock code).
5. Selected PDFs are downloaded one by one to that folder.

Replace:
- api/index.py
- add api/_hkex_search.py
- requirements.txt
- vercel.json

Delete old Blob engine files if they are no longer imported.

Test:
- /api/health -> 4.0
- / -> UI
- search 0066
- choose Downloads
- confirm 0066 folder creation
- try one PDF first

Note: direct browser fetch of HKEX PDF may be blocked by CORS. If so, use Open PDF and the next version can add a single-file helper.
