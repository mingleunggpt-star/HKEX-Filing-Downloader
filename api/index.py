from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from api._hkex_search import search_filings

app = FastAPI(title="HKEX Filing Downloader v4")

class SearchRequest(BaseModel):
    stock: str = Field(min_length=1, max_length=12)
    years: int = Field(default=6, ge=1, le=15)

@app.get("/api/health")
async def health():
    return {"ok": True, "service": "hkex-filing-downloader", "version": "4.0"}

@app.post("/api/search")
async def search(req: SearchRequest):
    try:
        return await search_filings(req.stock, req.years)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api", response_class=HTMLResponse)
async def home():
    return """<!doctype html>
<html lang="zh-HK"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HKEX Filing Downloader v4</title>
<style>
body{font-family:Arial;background:#f4f6f8;margin:0;color:#17212b}main{max-width:1050px;margin:40px auto;padding:20px}
.card{background:white;padding:28px;border:1px solid #dde3e9;border-radius:16px}
.grid{display:grid;grid-template-columns:1fr 160px 1fr;gap:14px}input,select,button{width:100%;padding:12px;font-size:16px;box-sizing:border-box}
button{border:0;border-radius:8px;font-weight:700;cursor:pointer}.primary{background:#172a3b;color:white}.secondary{background:#eaf0f4}.success{background:#177d4d;color:white}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}.actions button{width:auto}.hidden{display:none}.box{margin-top:16px;padding:12px;border-radius:8px;background:#edf3f7}.error{background:#fff0f0;color:#922}
.warn{background:#fff8e6;color:#725300}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}.metric{background:#f6f8fa;padding:12px;border-radius:8px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}.saved{color:#177d4d;font-weight:700}.failed{color:#a11;font-weight:700}
@media(max-width:800px){.grid{grid-template-columns:1fr}.summary{grid-template-columns:1fr 1fr}table{display:block;overflow-x:auto}}
</style></head><body><main><div class="card">
<h1>HKEX Filing Downloader</h1>
<p>先搜尋 HKEX 文件，再選擇本機 parent folder。系統會建立指定子資料夾並逐份儲存 PDF。</p>
<div class="grid">
<div><label>股票號碼</label><input id="stock" value="0066"></div>
<div><label>搜尋年期</label><select id="years"><option>5</option><option selected>6</option><option>7</option><option>10</option></select></div>
<div><label>資料夾名稱</label><input id="folderName" value="0066"></div>
</div>
<div class="actions">
<button id="searchBtn" class="primary">搜尋 HKEX 文件</button>
<button id="chooseBtn" class="secondary" disabled>選擇儲存位置</button>
<button id="downloadBtn" class="success" disabled>下載已選文件</button>
</div>
<div id="folderStatus" class="box hidden"></div><div id="status" class="box hidden"></div><div id="error" class="box error hidden"></div><div id="warn" class="box warn hidden"></div>
<section id="results" class="hidden"><h2 id="issuer"></h2>
<div class="summary"><div class="metric">找到<br><b id="found">0</b></div><div class="metric">已選<br><b id="selected">0</b></div><div class="metric">已儲存<br><b id="saved">0</b></div><div class="metric">失敗<br><b id="failed">0</b></div></div>
<div class="actions"><button id="allBtn" class="secondary">Select All</button><button id="noneBtn" class="secondary">Deselect All</button>
<label>已存在檔案：<select id="mode" style="width:auto"><option value="skip" selected>Skip</option><option value="replace">Replace</option><option value="rename">Rename</option></select></label></div>
<table><thead><tr><th></th><th>日期</th><th>類型</th><th>公告</th><th>狀態</th><th>HKEX</th></tr></thead><tbody id="rows"></tbody></table></section>
</div></main>
<script>
let docs=[], parentHandle=null, targetHandle=null, folderTouched=false;
const $=id=>document.getElementById(id), show=e=>e.classList.remove('hidden'), hide=e=>e.classList.add('hidden');
$('stock').addEventListener('input',()=>{if(!folderTouched)$('folderName').value=$('stock').value.trim()});
$('folderName').addEventListener('input',()=>folderTouched=true);
function safeName(s){return (s||'untitled').replace(/[<>:"/\\|?*\x00-\x1F]/g,'_').replace(/\s+/g,' ').trim().slice(0,120)}
function updateSelected(){const n=document.querySelectorAll('.doc-check:checked').length;$('selected').textContent=n;$('downloadBtn').disabled=!(n&&targetHandle)}
function render(){const tbody=$('rows');tbody.innerHTML='';docs.forEach((d,i)=>{const tr=document.createElement('tr');tr.innerHTML=`<td><input class="doc-check" data-i="${i}" type="checkbox" checked></td><td>${d.publication_date||''}</td><td>${d.document_type||''}</td><td></td><td id="st-${i}">Ready</td><td><a href="${d.source_url}" target="_blank">Open PDF</a></td>`;tr.children[3].textContent=d.title||'';tbody.appendChild(tr)});document.querySelectorAll('.doc-check').forEach(x=>x.addEventListener('change',updateSelected));$('found').textContent=docs.length;updateSelected()}
$('searchBtn').addEventListener('click',async()=>{hide($('error'));hide($('warn'));hide($('results'));show($('status'));$('status').textContent='正在搜尋 HKEX…';try{const r=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stock:$('stock').value.trim(),years:Number($('years').value)})});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Search failed');docs=d.documents||[];$('issuer').textContent=`${d.stock_code} — ${d.company}`;if(!folderTouched)$('folderName').value=$('stock').value.trim();render();hide($('status'));show($('results'));$('chooseBtn').disabled=false;if(!('showDirectoryPicker' in window)){show($('warn'));$('warn').textContent='此瀏覽器不支援本機資料夾寫入，請用最新版 Chrome 或 Edge。';$('chooseBtn').disabled=true}}catch(e){hide($('status'));show($('error'));$('error').textContent=e.message}});
$('chooseBtn').addEventListener('click',async()=>{try{parentHandle=await window.showDirectoryPicker({mode:'readwrite',startIn:'downloads'});targetHandle=await parentHandle.getDirectoryHandle(safeName($('folderName').value||$('stock').value||'HKEX'),{create:true});show($('folderStatus'));$('folderStatus').textContent=`已選 ${parentHandle.name}；子資料夾：${targetHandle.name}`;updateSelected()}catch(e){if(e.name!=='AbortError'){show($('error'));$('error').textContent=e.message}}});
$('allBtn').addEventListener('click',()=>{document.querySelectorAll('.doc-check').forEach(x=>x.checked=true);updateSelected()});
$('noneBtn').addEventListener('click',()=>{document.querySelectorAll('.doc-check').forEach(x=>x.checked=false);updateSelected()});
async function exists(dir,n){try{await dir.getFileHandle(n);return true}catch(e){if(e.name==='NotFoundError')return false;throw e}}
async function renameIfNeeded(dir,n){const p=n.lastIndexOf('.'),b=p>0?n.slice(0,p):n,e=p>0?n.slice(p):'';let i=2,c=n;while(await exists(dir,c)){c=`${b}_${i}${e}`;i++}return c}
async function save(dir,n,blob){const fh=await dir.getFileHandle(n,{create:true});const w=await fh.createWritable();await w.write(blob);await w.close()}
$('downloadBtn').addEventListener('click',async()=>{hide($('error'));hide($('warn'));const selected=[...document.querySelectorAll('.doc-check:checked')].map(x=>Number(x.dataset.i));let saved=0,failed=0;const mode=$('mode').value;$('downloadBtn').disabled=true;for(const i of selected){const d=docs[i],st=$(`st-${i}`);let name=safeName(`${d.stock_code||$('stock').value}_${d.publication_date||'unknown'}_${d.title||'filing'}.pdf`);st.textContent='Downloading…';try{const ex=await exists(targetHandle,name);if(ex&&mode==='skip'){st.textContent='Skipped';continue}if(ex&&mode==='rename')name=await renameIfNeeded(targetHandle,name);const r=await fetch(d.source_url,{mode:'cors',credentials:'omit'});if(!r.ok)throw new Error(`HTTP ${r.status}`);const blob=await r.blob();await save(targetHandle,name,blob);saved++;st.textContent='Saved';st.className='saved'}catch(e){failed++;st.textContent='Failed';st.className='failed';show($('warn'));$('warn').textContent='部分 HKEX PDF 可能被瀏覽器 CORS 規則阻擋；可先用 Open PDF。若實測如此，下一版會加單文件下載 helper。'}$('saved').textContent=saved;$('failed').textContent=failed}$('downloadBtn').disabled=false});
</script></body></html>"""
