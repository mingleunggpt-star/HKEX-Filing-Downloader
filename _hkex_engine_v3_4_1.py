from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from vercel import blob


BASE = "https://www1.hkexnews.hk"
PREFIX_URL = f"{BASE}/search/prefix.do"
SEARCH_URL = f"{BASE}/search/titleSearchServlet.do"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": f"{BASE}/search/titlesearch.xhtml",
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
}

SEARCH_T2_CODES = ["40100", "40200"]

FINANCIAL_TERMS = [
    "annual report", "interim report", "annual results", "final results",
    "interim results", "audited results",
    "年報", "年度報告", "中期報告",
    "全年業績", "年度業績", "末期業績", "中期業績", "經審核業績",
]

PROFIT_TERMS = [
    "profit warning", "profit alert", "positive profit alert",
    "expected loss", "expected profit",
    "reduction in loss", "increase in loss",
    "盈警", "盈喜", "盈利警告", "盈利預告",
    "預期虧損", "預期溢利", "減少虧損", "增加虧損",
]

SUPERSEDED_TERMS = [
    "cancelled since headlines superseded",
    "superseded and replaced",
    "superseded",
    "cancelled",
    "已被取代",
    "標題已被取代",
    "取消",
]


@dataclass
class Filing:
    record_id: str
    publication_date: str
    document_type: str
    title: str
    source_url: str
    is_superseded: bool = False
    status: str = "PENDING"
    size: int = 0
    sha256: str = ""
    download_url: str = ""
    blob_pathname: str = ""
    error: str = ""


def normalize_code(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits or len(digits) > 5:
        raise ValueError("HK stock code must contain 1-5 digits.")
    return digits.zfill(5)


def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def safe_name(text: str, length: int = 90) -> str:
    text = strip_html(text)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" ._")
    return (text[:length].rstrip() or "untitled")


def clean_jsonp(text: str) -> dict[str, Any]:
    m = re.search(r"^[^(]+\((.*)\)\s*;?\s*$", text.strip(), flags=re.S)
    if not m:
        raise RuntimeError("HKEX stock lookup response format changed.")
    return json.loads(m.group(1))


def normalize_url(link: str) -> str:
    link = html.unescape(link or "").strip()
    if not link:
        return ""
    if link.startswith(("http://", "https://")):
        return link
    if not link.startswith("/"):
        link = "/" + link
    return BASE + link


def get_field(item: dict[str, Any], *names: str) -> str:
    for name in names:
        value = item.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def parse_date(item: dict[str, Any]) -> str:
    raw = strip_html(get_field(item, "DATE_TIME", "RELEASE_TIME", "DATE"))

    patterns = [
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "DMY"),
        (r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", "YMD"),
    ]

    for pattern, order in patterns:
        m = re.search(pattern, raw)
        if not m:
            continue

        a, b, c = m.groups()

        if order == "DMY":
            d, mo, y = int(a), int(b), int(c)
        else:
            y, mo, d = int(a), int(b), int(c)

        return f"{y:04d}-{mo:02d}-{d:02d}"

    return "unknown-date"


async def resolve_stock(
    client: httpx.AsyncClient,
    code: str,
) -> tuple[str, str]:

    params = {
        "callback": "callback",
        "lang": "ZH",
        "type": "A",
        "name": code,
        "market": "SEHK",
    }

    response = await client.get(PREFIX_URL, params=params)
    response.raise_for_status()

    data = clean_jsonp(response.text)

    candidates = []

    for item in data.get("stockInfo", []):
        digits = re.sub(r"\D", "", str(item.get("code", "")))

        if digits and digits.zfill(5) == code:
            candidates.append(item)

    if not candidates:
        raise RuntimeError(f"Unable to resolve HKEX stock {code}.")

    item = candidates[0]

    stock_id = str(
        item.get("stockId")
        or item.get("stockID")
        or ""
    )

    if not stock_id:
        raise RuntimeError("HKEX returned no stockId.")

    company = (
        item.get("name")
        or item.get("shortName")
        or item.get("stockName")
        or code
    )

    return stock_id, safe_name(str(company), 60)


async def search_t2(
    client: httpx.AsyncClient,
    stock_id: str,
    t2code: str,
    from_date: str,
    to_date: str,
) -> list[dict[str, Any]]:

    params = {
        "sortDir": "1",
        "sortByOptions": "DateTime",
        "category": "0",
        "market": "SEHK",
        "stockId": stock_id,
        "documentType": "-1",
        "fromDate": from_date,
        "toDate": to_date,
        "title": "",
        "searchType": "1",
        "t1code": "40000",
        "t2Gcode": "-2",
        "t2code": t2code,
        "rowRange": "2000",
        "lang": "zh",
    }

    response = await client.get(SEARCH_URL, params=params)
    response.raise_for_status()

    outer = response.json()
    result = outer.get("result", [])

    if isinstance(result, str):
        result = json.loads(result)

    if isinstance(result, dict):
        for key in ("records", "data", "items", "result"):
            if isinstance(result.get(key), list):
                return result[key]
        return []

    return result if isinstance(result, list) else []


def classify(item: dict[str, Any]) -> str | None:
    meta = " | ".join(
        strip_html(str(item.get(k, "")))
        for k in ("TITLE", "CATEGORY", "LONG_TEXT", "FILE_INFO", "TIER2_NAME")
    ).lower()

    if any(term.lower() in meta for term in PROFIT_TERMS):
        return "profit-alert"

    if any(term.lower() in meta for term in FINANCIAL_TERMS):
        if "interim" in meta or "中期" in meta:
            return "interim"

        if (
            "annual report" in meta
            or "年報" in meta
            or "年度報告" in meta
        ):
            return "annual-report"

        return "results"

    return None


def is_superseded(item: dict[str, Any]) -> bool:
    meta = " | ".join(str(v) for v in item.values()).lower()
    return any(term.lower() in meta for term in SUPERSEDED_TERMS)


def build_filings(
    code: str,
    items: list[dict[str, Any]],
) -> list[Filing]:

    out: list[Filing] = []
    seen_urls: set[str] = set()

    for item in items:
        doc_type = classify(item)

        if not doc_type:
            continue

        url = normalize_url(
            get_field(item, "FILE_LINK", "fileLink", "url")
        )

        title = strip_html(
            get_field(item, "TITLE", "title")
        )

        if not url or url in seen_urls:
            continue

        pub_date = parse_date(item)

        record_id = hashlib.sha1(
            f"{code}|{pub_date}|{url}".encode("utf-8")
        ).hexdigest()[:14]

        superseded = is_superseded(item)

        out.append(
            Filing(
                record_id=record_id,
                publication_date=pub_date,
                document_type=doc_type,
                title=title,
                source_url=url,
                is_superseded=superseded,
                status=(
                    "SKIPPED_SUPERSEDED"
                    if superseded
                    else "PENDING"
                ),
            )
        )

        seen_urls.add(url)

    out.sort(
        key=lambda filing: filing.publication_date,
        reverse=True,
    )

    return out


async def download_pdf(
    client: httpx.AsyncClient,
    url: str,
    destination: Path,
) -> None:

    async with client.stream(
        "GET",
        url,
        headers={"Accept": "application/pdf,*/*"},
    ) as response:

        response.raise_for_status()

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with destination.open("wb") as handle:
            async for chunk in response.aiter_bytes(1024 * 256):
                handle.write(chunk)

    if not destination.exists() or destination.stat().st_size < 100:
        raise RuntimeError("Downloaded PDF is unexpectedly small.")

    with destination.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise RuntimeError("HKEX response is not a valid PDF.")


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            hasher.update(chunk)

    return hasher.hexdigest()


def extract_blob_value(
    uploaded: Any,
    *names: str,
) -> str:

    if isinstance(uploaded, dict):
        for name in names:
            value = uploaded.get(name)
            if value:
                return str(value)

    for name in names:
        value = getattr(uploaded, name, None)
        if value:
            return str(value)

    return ""


def upload_blob_sync(
    local_path: Path,
    pathname: str,
) -> tuple[str, str]:

    uploaded = blob.upload_file(
        local_path=str(local_path),
        path=pathname,
        access="public",
    )

    download_url = extract_blob_value(
        uploaded,
        "download_url",
        "downloadUrl",
        "url",
    )

    blob_pathname = extract_blob_value(
        uploaded,
        "pathname",
        "path",
    )

    if not download_url:
        raise RuntimeError(
            "Blob upload completed but no download URL was returned."
        )

    return download_url, blob_pathname


async def upload_blob(
    local_path: Path,
    pathname: str,
) -> tuple[str, str]:

    return await asyncio.to_thread(
        upload_blob_sync,
        local_path,
        pathname,
    )


async def run_download(
    stock: str,
    years: int,
) -> dict[str, Any]:

    code = normalize_code(stock)

    if years < 1 or years > 15:
        raise ValueError("years must be between 1 and 15.")

    today = date.today()

    from_date = f"{max(1999, today.year - years)}0101"
    to_date = today.strftime("%Y%m%d")

    timeout = httpx.Timeout(
        60.0,
        connect=20.0,
    )

    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=timeout,
        follow_redirects=True,
        http2=True,
    ) as http:

        stock_id, company = await resolve_stock(
            http,
            code,
        )

        result_sets = await asyncio.gather(
            *[
                search_t2(
                    http,
                    stock_id,
                    t2code,
                    from_date,
                    to_date,
                )
                for t2code in SEARCH_T2_CODES
            ]
        )

        items = [
            item
            for group in result_sets
            for item in group
        ]

        filings = build_filings(
            code,
            items,
        )

        with tempfile.TemporaryDirectory() as temp_dir:

            work = Path(temp_dir)
            raw_dir = work / "raw"
            manifest_path = work / "manifest.json"

            for filing in filings:

                if filing.is_superseded:
                    continue

                filename = (
                    f"{code}_"
                    f"{filing.publication_date}_"
                    f"{safe_name(filing.title, 80)}"
                    f".pdf"
                )

                local_path = raw_dir / filename

                try:
                    await download_pdf(
                        http,
                        filing.source_url,
                        local_path,
                    )

                    filing.size = local_path.stat().st_size
                    filing.sha256 = sha256_file(local_path)

                    pathname = (
                        f"HKEX/"
                        f"{code}_{company}/"
                        f"{filing.publication_date}/"
                        f"{filename}"
                    )

                    (
                        filing.download_url,
                        filing.blob_pathname,
                    ) = await upload_blob(
                        local_path,
                        pathname,
                    )

                    filing.status = "DOWNLOADED"

                except Exception as error:
                    filing.status = "FAILED"
                    filing.error = str(error)

            manifest = {
                "stock_code": code,
                "company": company,
                "search_from": from_date,
                "search_to": to_date,
                "documents": [
                    asdict(filing)
                    for filing in filings
                ],
            }

            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            zip_name = (
                f"{code}_"
                f"{company}_"
                f"HKEX_Filings.zip"
            )

            zip_path = work / zip_name

            with zipfile.ZipFile(
                zip_path,
                "w",
                zipfile.ZIP_DEFLATED,
            ) as archive:

                if raw_dir.exists():
                    for pdf in raw_dir.rglob("*.pdf"):
                        archive.write(
                            pdf,
                            Path("raw") / pdf.name,
                        )

                archive.write(
                    manifest_path,
                    "manifest.json",
                )

            (
                zip_download_url,
                zip_blob_pathname,
            ) = await upload_blob(
                zip_path,
                (
                    f"HKEX/"
                    f"{code}_{company}/"
                    f"{zip_name}"
                ),
            )

        downloaded = sum(
            1
            for filing in filings
            if filing.status == "DOWNLOADED"
        )

        failed = sum(
            1
            for filing in filings
            if filing.status == "FAILED"
        )

        return {
            "stock_code": code,
            "company": company,
            "search_from": from_date,
            "search_to": to_date,
            "total_documents": len(filings),
            "downloaded": downloaded,
            "failed": failed,
            "zip_download_url": zip_download_url,
            "zip_blob_pathname": zip_blob_pathname,
            "documents": [
                asdict(filing)
                for filing in filings
            ],
        }
