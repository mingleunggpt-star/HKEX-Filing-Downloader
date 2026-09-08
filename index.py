from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from _hkex_engine import run_download

app = FastAPI(title='HKEX Filing Downloader')

class DownloadRequest(BaseModel):
    stock: str = Field(min_length=1, max_length=12)
    years: int = Field(default=6, ge=1, le=15)

@app.get('/api', response_class=HTMLResponse)
async def home():
    return '''<!doctype html><html lang="zh-HK"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HKEX Filing Downloader</title><style>body{font-family:Arial,sans-serif;background:#f4f6f8;margin:0;color:#17212b}main{max-width:900px;margin:50px auto;padding:20px}.card{background:#fff;border:1px solid #dde3e9;border-radius:16px;padding:30px}.grid{display:grid;grid-template-columns:1fr 180px;gap:16px}input,select,button{width:100%;padding:12px;font-size:16px;box-sizing:border-box}button{grid-column:1/-1;background:#172a3b;color:#fff;border:0;border-radius:8px;font-weight:700}.hidden{display:none}.box{margin-top:20px;padding:14px;border-radius:8px;background:#edf3f7}.error{background:#fff0f0;color:#922}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}.metric{background:#f6f8fa;padding:14px;border-radius:8px}table{width:100%;border-collapse:collapse;margin-top:18px;font-size:13px}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}</style></head><body><main><div class="card"><h1>HKEX Filing Downloader</h1><p>輸入香港股票號碼，一鍵搜尋 HKEX 官方財務公告並建立 ZIP。</p><form id="f"><div class="grid"><input id="stock" value="0066" placeholder="0066 / 0700 / 0005"><select id="years"><option>5</option><option selected>6</option><option>7</option><option>10</option></select><button id="btn">下載 HKEX Filings</button></div></form><div id="status" class="box hidden"></div><div id="err" class="box error hidden"></div><section id="result" class="hidden"><h2 id="issuer"></h2><div class="metrics"><div class="metric">找到文件<br><b id="total">0</b></div><div class="metric">成功下載<br><b id="downloaded">0</b></div><div class="metric">失敗<br><b id="failed">0</b></div></div><p><a id="zip" target="_blank">下載全部 ZIP</a></p><table><thead><tr><th>日期</th><th>類型</th><th>公告</th><th>狀態</th><th>PDF</th></tr></thead><tbody id="rows"></tbody></table></section></div></main><script>const f=document.getElementById('f'),btn=document.getElementById('btn'),status=document.getElementById('status'),err=document.getElementById('err'),result=document.getElementById('result');const show=x=>x.classList.remove('hidden'),hide=x=>x.classList.add('hidden');f.addEventListener('submit',async e=>{e.preventDefault();hide(err);hide(result);show(status);status.textContent='正在搜尋 HKEX、下載 PDF、上載 Blob 及建立 ZIP，可能需數分鐘…';btn.disabled=true;try{const r=await fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stock:document.getElementById('stock').value.trim(),years:Number(document.getElementById('years').value)})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Download failed');document.getElementById('issuer').textContent=`${d.stock_code} — ${d.company}`;document.getElementById('total').textContent=d.total_documents||0;document.getElementById('downloaded').textContent=d.downloaded||0;document.getElementById('failed').textContent=d.failed||0;document.getElementById('zip').href=d.zip_download_url||'#';const rows=document.getElementById('rows');rows.innerHTML='';(d.documents||[]).forEach(x=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${x.publication_date||''}</td><td>${x.document_type||''}</td><td>${x.title||''}</td><td>${x.status||''}</td><td>${x.download_url?`<a href="${x.download_url}" target="_blank">PDF</a>`:''}</td>`;rows.appendChild(tr)});hide(status);show(result)}catch(ex){hide(status);err.textContent=ex.message||String(ex);show(err)}finally{btn.disabled=false}});</script></body></html>'''

@app.get('/api/health')
async def health():
    return {'ok': True, 'service': 'hkex-filing-downloader', 'version': '3.5'}

@app.post('/api/download')
async def download(req: DownloadRequest, request: Request):
    oidc_token = request.headers.get('x-vercel-oidc-token')
    if not oidc_token:
        raise HTTPException(status_code=500, detail='Vercel OIDC token header is missing. Check Project Settings > Security > OIDC federation.')
    try:
        return await run_download(req.stock, req.years, oidc_token=oidc_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
