from __future__ import annotations
import hashlib, html, json, re
from datetime import date
from typing import Any
import httpx

BASE="https://www1.hkexnews.hk"
PREFIX_URL=f"{BASE}/search/prefix.do"
SEARCH_URL=f"{BASE}/search/titleSearchServlet.do"
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)","Accept":"application/json,text/plain,*/*","Referer":f"{BASE}/search/titlesearch.xhtml","Accept-Language":"zh-HK,zh;q=0.9,en;q=0.8"}
SEARCH_T2_CODES=["40100","40200"]
FINANCIAL_TERMS=["annual report","interim report","annual results","final results","interim results","audited results","年報","年度報告","中期報告","全年業績","年度業績","末期業績","中期業績","經審核業績"]
PROFIT_TERMS=["profit warning","profit alert","positive profit alert","expected loss","expected profit","reduction in loss","increase in loss","盈警","盈喜","盈利警告","盈利預告","預期虧損","預期溢利","減少虧損","增加虧損"]
SUPERSEDED_TERMS=["cancelled since headlines superseded","superseded and replaced","superseded","cancelled","已被取代","標題已被取代","取消"]

def normalize_code(raw):
    d=re.sub(r"\D","",raw or "")
    if not d or len(d)>5: raise ValueError("HK stock code must contain 1-5 digits.")
    return d.zfill(5)

def strip_html(t):
    t=html.unescape(t or "");t=re.sub(r"<br\s*/?>"," ",t,flags=re.I);t=re.sub(r"<[^>]+>","",t);return re.sub(r"\s+"," ",t).strip()

def clean_jsonp(t):
    m=re.search(r"^[^(]+\((.*)\)\s*;?\s*$",t.strip(),flags=re.S)
    if not m: raise RuntimeError("HKEX stock lookup response format changed.")
    return json.loads(m.group(1))

def norm_url(link):
    link=html.unescape(link or "").strip()
    if not link:return ""
    if link.startswith(("http://","https://")):return link
    return BASE+(link if link.startswith("/") else "/"+link)

def field(item,*names):
    for n in names:
        v=item.get(n)
        if v not in (None,""):return str(v)
    return ""

def parse_date(item):
    raw=strip_html(field(item,"DATE_TIME","RELEASE_TIME","DATE"))
    for pat,order in [(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})","DMY"),(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})","YMD")]:
        m=re.search(pat,raw)
        if m:
            a,b,c=m.groups()
            if order=="DMY":d,mo,y=int(a),int(b),int(c)
            else:y,mo,d=int(a),int(b),int(c)
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return "unknown-date"

async def resolve_stock(client,code):
    r=await client.get(PREFIX_URL,params={"callback":"callback","lang":"ZH","type":"A","name":code,"market":"SEHK"});r.raise_for_status();data=clean_jsonp(r.text)
    for item in data.get("stockInfo",[]):
        d=re.sub(r"\D","",str(item.get("code","")))
        if d and d.zfill(5)==code:
            stock_id=str(item.get("stockId") or item.get("stockID") or "")
            company=item.get("name") or item.get("shortName") or item.get("stockName") or code
            if not stock_id:raise RuntimeError("HKEX returned no stockId.")
            return stock_id,strip_html(str(company))
    raise RuntimeError(f"Unable to resolve HKEX stock {code}.")

async def search_t2(client,stock_id,t2,from_date,to_date):
    p={"sortDir":"1","sortByOptions":"DateTime","category":"0","market":"SEHK","stockId":stock_id,"documentType":"-1","fromDate":from_date,"toDate":to_date,"title":"","searchType":"1","t1code":"40000","t2Gcode":"-2","t2code":t2,"rowRange":"2000","lang":"zh"}
    r=await client.get(SEARCH_URL,params=p);r.raise_for_status();o=r.json();res=o.get("result",[])
    if isinstance(res,str):res=json.loads(res)
    if isinstance(res,dict):
        for k in ("records","data","items","result"):
            if isinstance(res.get(k),list):return res[k]
        return []
    return res if isinstance(res,list) else []

def classify(item):
    meta=" | ".join(strip_html(str(item.get(k,""))) for k in ("TITLE","CATEGORY","LONG_TEXT","FILE_INFO","TIER2_NAME")).lower()
    if any(t.lower() in meta for t in PROFIT_TERMS):return "profit-alert"
    if any(t.lower() in meta for t in FINANCIAL_TERMS):
        if "interim" in meta or "中期" in meta:return "interim"
        if "annual report" in meta or "年報" in meta or "年度報告" in meta:return "annual-report"
        return "results"
    return None

def superseded(item):
    meta=" | ".join(str(v) for v in item.values()).lower();return any(t.lower() in meta for t in SUPERSEDED_TERMS)

def build_docs(code,items):
    out=[];seen=set()
    for item in items:
        typ=classify(item)
        if not typ:continue
        url=norm_url(field(item,"FILE_LINK","fileLink","url"));title=strip_html(field(item,"TITLE","title"))
        if not url or url in seen:continue
        pub=parse_date(item);rid=hashlib.sha1(f"{code}|{pub}|{url}".encode()).hexdigest()[:14]
        out.append({"record_id":rid,"stock_code":code,"publication_date":pub,"document_type":typ,"title":title,"source_url":url,"is_superseded":superseded(item)})
        seen.add(url)
    out.sort(key=lambda x:x["publication_date"],reverse=True);return out

async def search_filings(stock:str,years:int)->dict[str,Any]:
    code=normalize_code(stock);today=date.today();from_date=f"{max(1999,today.year-years)}0101";to_date=today.strftime("%Y%m%d")
    async with httpx.AsyncClient(headers=HEADERS,timeout=httpx.Timeout(45,connect=20),follow_redirects=True,http2=True) as client:
        stock_id,company=await resolve_stock(client,code);items=[]
        for t2 in SEARCH_T2_CODES:items.extend(await search_t2(client,stock_id,t2,from_date,to_date))
        docs=build_docs(code,items)
        return {"stock_code":code,"company":company,"search_from":from_date,"search_to":to_date,"documents_found":len(docs),"documents":docs}
