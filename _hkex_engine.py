from __future__ import annotations
import asyncio, hashlib, html, json, re, tempfile, zipfile
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any
import httpx
from vercel import blob

BASE="https://www1.hkexnews.hk"
PREFIX_URL=f"{BASE}/search/prefix.do"
SEARCH_URL=f"{BASE}/search/titleSearchServlet.do"
HEADERS={"User-Agent":"Mozilla/5.0","Accept":"application/json,text/plain,*/*","Referer":f"{BASE}/search/titlesearch.xhtml","Accept-Language":"zh-HK,zh;q=0.9,en;q=0.8"}
SEARCH_T2_CODES=["40100","40200"]
FINANCIAL_TERMS=["annual report","interim report","annual results","final results","interim results","audited results","年報","年度報告","中期報告","全年業績","年度業績","末期業績","中期業績","經審核業績"]
PROFIT_TERMS=["profit warning","profit alert","positive profit alert","expected loss","expected profit","reduction in loss","increase in loss","盈警","盈喜","盈利警告","盈利預告","預期虧損","預期溢利","減少虧損","增加虧損"]
SUPERSEDED_TERMS=["cancelled since headlines superseded","superseded and replaced","superseded","cancelled","已被取代","標題已被取代","取消"]

@dataclass
class Filing:
    record_id:str
    publication_date:str
    document_type:str
    title:str
    source_url:str
    is_superseded:bool=False
    status:str="PENDING"
    size:int=0
    sha256:str=""
    download_url:str=""
    blob_pathname:str=""
    error:str=""

def normalize_code(raw:str)->str:
    d=re.sub(r"\D","",raw or "")
    if not d or len(d)>5: raise ValueError("HK stock code must contain 1-5 digits.")
    return d.zfill(5)

def strip_html(t:str)->str:
    t=html.unescape(t or "")
    t=re.sub(r"<br\s*/?>"," ",t,flags=re.I)
    t=re.sub(r"<[^>]+>","",t)
    return re.sub(r"\s+"," ",t).strip()

def safe_name(t:str,n:int=90)->str:
    t=strip_html(t)
    t=re.sub(r'[<>:"/\\|?*\x00-\x1f]',"_",t)
    t=re.sub(r"\s+"," ",t).strip(" ._")
    return (t[:n].rstrip() or "untitled")

def clean_jsonp(text:str)->dict[str,Any]:
    m=re.search(r"^[^(]+\((.*)\)\s*;?\s*$",text.strip(),flags=re.S)
    if not m: raise RuntimeError("HKEX stock lookup response format changed.")
    return json.loads(m.group(1))

def normalize_url(link:str)->str:
    link=html.unescape(link or "").strip()
    if not link: return ""
    if link.startswith(("http://","https://")): return link
    return BASE + (link if link.startswith("/") else "/"+link)

def get_field(item:dict[str,Any],*names:str)->str:
    for n in names:
        v=item.get(n)
        if v not in (None,""): return str(v)
    return ""

def parse_date(item:dict[str,Any])->str:
    raw=strip_html(get_field(item,"DATE_TIME","RELEASE_TIME","DATE"))
    for pat,order in [(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})","DMY"),(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})","YMD")]:
        m=re.search(pat,raw)
        if m:
            a,b,c=m.groups()
            if order=="DMY": d,mo,y=int(a),int(b),int(c)
            else: y,mo,d=int(a),int(b),int(c)
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return "unknown-date"

async def resolve_stock(client:httpx.AsyncClient,code:str)->tuple[str,str]:
    p={"callback":"callback","lang":"ZH","type":"A","name":code,"market":"SEHK"}
    r=await client.get(PREFIX_URL,params=p); r.raise_for_status()
    data=clean_jsonp(r.text)
    cand=[]
    for item in data.get("stockInfo",[]):
        d=re.sub(r"\D","",str(item.get("code","")))
        if d and d.zfill(5)==code: cand.append(item)
    if not cand: raise RuntimeError(f"Unable to resolve HKEX stock {code}.")
    item=cand[0]
    stock_id=str(item.get("stockId") or item.get("stockID") or "")
    if not stock_id: raise RuntimeError("HKEX returned no stockId.")
    company=item.get("name") or item.get("shortName") or item.get("stockName") or code
    return stock_id,safe_name(str(company),60)

async def search_t2(client:httpx.AsyncClient,stock_id:str,t2code:str,from_date:str,to_date:str):
    p={"sortDir":"1","sortByOptions":"DateTime","category":"0","market":"SEHK","stockId":stock_id,"documentType":"-1","fromDate":from_date,"toDate":to_date,"title":"","searchType":"1","t1code":"40000","t2Gcode":"-2","t2code":t2code,"rowRange":"2000","lang":"zh"}
    r=await client.get(SEARCH_URL,params=p); r.raise_for_status()
    outer=r.json(); result=outer.get("result",[])
    if isinstance(result,str): result=json.loads(result)
    if isinstance(result,dict):
        for k in ("records","data","items","result"):
            if isinstance(result.get(k),list): return result[k]
        return []
    return result if isinstance(result,list) else []

def classify(item):
    meta=" | ".join(strip_html(str(item.get(k,""))) for k in ("TITLE","CATEGORY","LONG_TEXT","FILE_INFO","TIER2_NAME")).lower()
    if any(t.lower() in meta for t in PROFIT_TERMS): return "profit-alert"
    if any(t.lower() in meta for t in FINANCIAL_TERMS):
        if "interim" in meta or "中期" in meta: return "interim"
        if "annual report" in meta or "年報" in meta or "年度報告" in meta: return "annual-report"
        return "results"
    return None

def is_superseded(item):
    meta=" | ".join(str(v) for v in item.values()).lower()
    return any(t.lower() in meta for t in SUPERSEDED_TERMS)

def build_filings(code,items):
    out=[]; seen=set()
    for item in items:
        typ=classify(item)
        if not typ: continue
        url=normalize_url(get_field(item,"FILE_LINK","fileLink","url"))
        title=strip_html(get_field(item,"TITLE","title"))
        if not url or url in seen: continue
        pub=parse_date(item)
        rid=hashlib.sha1(f"{code}|{pub}|{url}".encode()).hexdigest()[:14]
        sup=is_superseded(item)
        out.append(Filing(rid,pub,typ,title,url,sup,"SKIPPED_SUPERSEDED" if sup else "PENDING"))
        seen.add(url)
    out.sort(key=lambda x:x.publication_date,reverse=True)
    return out

async def download_pdf(client,url,dest:Path):
    async with client.stream("GET",url,headers={"Accept":"application/pdf,*/*"}) as r:
        r.raise_for_status(); dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open("wb") as f:
            async for chunk in r.aiter_bytes(1024*256): f.write(chunk)
    if not dest.exists() or dest.stat().st_size<100: raise RuntimeError("Downloaded PDF is unexpectedly small.")
    with dest.open("rb") as f:
        if f.read(5)!=b"%PDF-": raise RuntimeError("HKEX response is not a valid PDF.")

def sha256_file(path:Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def _blob_value(uploaded, *names):
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


def _upload_blob_sync(local_path: Path, pathname: str, access: str = "public"):
    """Upload with Vercel Python SDK using project OIDC credentials.

    When the Blob store is connected to the Vercel project, Vercel provides
    BLOB_STORE_ID plus a short-lived VERCEL_OIDC_TOKEN automatically.
    No long-lived BLOB_READ_WRITE_TOKEN is required.
    """
    uploaded = blob.upload_file(
        local_path=str(local_path),
        path=pathname,
        access=access,
    )
    download_url = _blob_value(uploaded, "download_url", "downloadUrl", "url")
    blob_pathname = _blob_value(uploaded, "pathname", "path")
    if not download_url:
        raise RuntimeError("Vercel Blob upload returned no download URL.")
    return download_url, blob_pathname


async def upload_blob(local_path: Path, pathname: str, access: str = "public"):
    return await asyncio.to_thread(
        _upload_blob_sync,
        local_path,
        pathname,
        access,
    )


async def run_download(stock:str,years:int):
    code=normalize_code(stock)
    today=date.today()
    from_date=f"{max(1999,today.year-years)}0101"; to_date=today.strftime("%Y%m%d")
    async with httpx.AsyncClient(headers=HEADERS,timeout=httpx.Timeout(60.0,connect=20.0),follow_redirects=True,http2=True) as http:
        stock_id,company=await resolve_stock(http,code)
        groups=await asyncio.gather(*[search_t2(http,stock_id,t,from_date,to_date) for t in SEARCH_T2_CODES])
        filings=build_filings(code,[i for g in groups for i in g])
        blob=AsyncBlobClient()
        with tempfile.TemporaryDirectory() as td:
            work=Path(td); raw=work/"raw"; manifest=work/"manifest.json"
            for f in filings:
                if f.is_superseded: continue
                filename=f"{code}_{f.publication_date}_{safe_name(f.title,80)}.pdf"; local=raw/filename
                try:
                    await download_pdf(http,f.source_url,local)
                    f.size=local.stat().st_size; f.sha256=sha256_file(local)
                    up=await upload_blob(blob,f"HKEX/{code}_{company}/{f.publication_date}/{filename}",local,"application/pdf")
                    f.download_url=up.download_url; f.blob_pathname=up.pathname; f.status="DOWNLOADED"
                except Exception as e:
                    f.status="FAILED"; f.error=str(e)
            manifest.write_text(json.dumps({"stock_code":code,"company":company,"search_from":from_date,"search_to":to_date,"documents":[asdict(f) for f in filings]},ensure_ascii=False,indent=2),encoding="utf-8")
            zip_name=f"{code}_{company}_HKEX_Filings.zip"; zip_path=work/zip_name
            with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
                if raw.exists():
                    for pdf in raw.rglob("*.pdf"): z.write(pdf,Path("raw")/pdf.name)
                z.write(manifest,"manifest.json")
            zu=await upload_blob(blob,f"HKEX/{code}_{company}/{zip_name}",zip_path,"application/zip")
        return {"stock_code":code,"company":company,"search_from":from_date,"search_to":to_date,"total_documents":len(filings),"downloaded":sum(f.status=="DOWNLOADED" for f in filings),"failed":sum(f.status=="FAILED" for f in filings),"zip_download_url":zu.download_url,"documents":[asdict(f) for f in filings]}
