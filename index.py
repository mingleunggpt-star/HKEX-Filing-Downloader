from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from _hkex_engine import run_download

app = FastAPI(title="HKEX Filing Downloader")

class DownloadRequest(BaseModel):
    stock: str = Field(min_length=1, max_length=12)
    years: int = Field(default=6, ge=1, le=15)

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!doctype html>
    <html lang="zh-HK">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>HKEX Filing Downloader</title>
      <style>
        body{font-family:Arial,sans-serif;background:#f4f6f8;margin:0;color:#17212b}
        main{max-width:900px;margin:50px auto;padding:20px}
        .card{background:#fff;border:1px solid #dde3e9;border-radius:16px;padding:30px;box-shadow:0 10px 30px rgba(0,0,0,.06)}
        h1{margin-top:0;font-size:34px}
        .intro{color:#5d6b78;line-height:1.7}
        .grid{display:grid;grid-template-columns:1fr 180px;gap:16px;margin-top:25px}
        label{display:block;font-weight:700;margin-bottom:6px}
        input,select{width:100%;padding:12px;font-size:16px;border:1px solid #c7d0d9;border-radius:8px;box-sizing:border-box}
        button{grid-column:1/-1;padding:13px 18px;border:none;border-radius:8px;background:#172a3b;color:white;font-weight:700;font-size:16px;cursor:pointer}
        button:disabled{opacity:.55;cursor:wait}
        .box{margin-top:20px;padding:14px;border-radius:8px;background:#edf3f7}
        .error{background:#fff0f0;color:#922}
        .hidden{display:none}
        .result{margin-top:28px;border-top:1px solid #e2e7eb;padding-top:22px}
        .metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}
        .metric{background:#f6f8fa;border-radius:8px;padding:15px}
        .metric span{display:block;color:#6d7985;font-size:12px}
        .metric strong{font-size:24px}
        .zip-link{display:inline-block;padding:12px 16px;background:#177d4d;color:white;text-decoration:none;border-radius:8px;font-weight:700;margin-bottom:20px}
        table{width:100%;border-collapse:collapse;margin-top:14px;font-size:13px}
        th,td{padding:9px;border-bottom:1px solid #e1e6ea;text-align:left;vertical-align:top}
        th{background:#f7f9fa}
        .badge{display:inline-block;background:#edf2f6;padding:3px 8px;border-radius:999px;font-size:11px}
        .small{font-size:12px;color:#6c7884}
        @media(max-width:650px){.grid{grid-template-columns:1fr}.metrics{grid-template-columns:1fr}table{display:block;overflow-x:auto}}
      </style>
    </head>
    <body>
      <main>
        <div class="card">
          <h1>HKEX Filing Downloader</h1>
          <p class="intro">輸入香港股票號碼，一鍵搜尋 HKEX 官方財務公告、下載 raw PDF、上載到 Vercel Blob，並建立 ZIP。</p>
          <form id="downloadForm">
            <div class="grid">
              <div>
                <label for="stock">股票號碼</label>
                <input id="stock" value="0066" placeholder="例如 0066、0700、0005">
              </div>
              <div>
                <label for="years">搜尋年期</label>
                <select id="years">
                  <option value="5">5 年</option>
                  <option value="6" selected>6 年</option>
                  <option value="7">7 年</option>
                  <option value="10">10 年</option>
                </select>
              </div>
              <button id="runButton" type="submit">下載 HKEX Filings</button>
            </div>
          </form>

          <div id="statusBox" class="box hidden"></div>
          <div id="errorBox" class="box error hidden"></div>

          <section id="resultBox" class="result hidden">
            <h2 id="issuer"></h2>
            <div class="metrics">
              <div class="metric"><span>找到文件</span><strong id="total">0</strong></div>
              <div class="metric"><span>成功下載</span><strong id="downloaded">0</strong></div>
              <div class="metric"><span>失敗</span><strong id="failed">0</strong></div>
            </div>
            <a id="zipLink" class="zip-link" target="_blank" rel="noopener">下載全部 ZIP</a>
            <p id="period" class="small"></p>
            <table>
              <thead><tr><th>日期</th><th>類型</th><th>公告</th><th>狀態</th><th>PDF</th></tr></thead>
              <tbody id="rows"></tbody>
            </table>
          </section>
        </div>
      </main>
      <script>
        const form=document.getElementById("downloadForm");
        const runButton=document.getElementById("runButton");
        const statusBox=document.getElementById("statusBox");
        const errorBox=document.getElementById("errorBox");
        const resultBox=document.getElementById("resultBox");
        const show=(el)=>el.classList.remove("hidden");
        const hide=(el)=>el.classList.add("hidden");

        form.addEventListener("submit", async (event)=>{
          event.preventDefault();
          hide(errorBox); hide(resultBox); show(statusBox);
          statusBox.textContent="正在搜尋 HKEX、下載 PDF、驗證文件、上載 Vercel Blob 及建立 ZIP。大型年報可能需要數分鐘。";
          runButton.disabled=true;
          runButton.textContent="處理中…";

          try{
            const stock=document.getElementById("stock").value.trim();
            const years=Number(document.getElementById("years").value);

            const response=await fetch("/api/download",{
              method:"POST",
              headers:{"Content-Type":"application/json"},
              body:JSON.stringify({stock,years})
            });

            const data=await response.json();
            if(!response.ok) throw new Error(data.detail || "Download failed.");

            document.getElementById("issuer").textContent=`${data.stock_code} — ${data.company}`;
            document.getElementById("total").textContent=data.total_documents ?? 0;
            document.getElementById("downloaded").textContent=data.downloaded ?? 0;
            document.getElementById("failed").textContent=data.failed ?? 0;
            document.getElementById("period").textContent=`Search period: ${data.search_from || ""} → ${data.search_to || ""}`;

            const zipLink=document.getElementById("zipLink");
            if(data.zip_download_url){
              zipLink.href=data.zip_download_url;
              zipLink.style.display="inline-block";
            }else{
              zipLink.style.display="none";
            }

            const rows=document.getElementById("rows");
            rows.innerHTML="";
            (data.documents || []).forEach((doc)=>{
              const tr=document.createElement("tr");
              const td1=document.createElement("td"); td1.textContent=doc.publication_date || "";
              const td2=document.createElement("td");
              const badge=document.createElement("span"); badge.className="badge"; badge.textContent=doc.document_type || "";
              td2.appendChild(badge);
              const td3=document.createElement("td"); td3.textContent=doc.title || "";
              const td4=document.createElement("td"); td4.textContent=doc.status || "";
              const td5=document.createElement("td");
              if(doc.download_url){
                const a=document.createElement("a");
                a.href=doc.download_url; a.target="_blank"; a.rel="noopener"; a.textContent="PDF";
                td5.appendChild(a);
              }
              tr.append(td1,td2,td3,td4,td5);
              rows.appendChild(tr);
            });

            hide(statusBox); show(resultBox);

          }catch(error){
            hide(statusBox);
            errorBox.textContent=error.message || String(error);
            show(errorBox);
          }finally{
            runButton.disabled=false;
            runButton.textContent="下載 HKEX Filings";
          }
        });
      </script>
    </body>
    </html>
    """

@app.get("/api/health")
async def health():
    return {"ok": True, "service": "hkex-filing-downloader", "version": "3.2"}

@app.post("/api/download")
async def download(req: DownloadRequest):
    try:
        return await run_download(req.stock, req.years)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
