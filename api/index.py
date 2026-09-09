from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from _hkex_search import search_filings

app = FastAPI(title="HKEX Filing Downloader v4.0.2")


class SearchRequest(BaseModel):
    stock: str = Field(min_length=1, max_length=12)
    years: int = Field(default=6, ge=1, le=15)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "service": "hkex-filing-downloader",
        "version": "4.0.2"
    }


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
    return HTML_PAGE


HTML_PAGE = r"""
<!doctype html>
<html lang="zh-HK">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HKEX Filing Downloader v4.0.2</title>

<style>
body{
  font-family:Arial,sans-serif;
  background:#f4f6f8;
  margin:0;
  color:#17212b
}
main{
  max-width:1050px;
  margin:40px auto;
  padding:20px
}
.card{
  background:#fff;
  padding:28px;
  border:1px solid #dde3e9;
  border-radius:16px
}
.grid{
  display:grid;
  grid-template-columns:1fr 160px 1fr;
  gap:14px
}
label{
  display:block;
  margin-bottom:6px;
  font-weight:700
}
input,select,button{
  width:100%;
  padding:12px;
  font-size:16px;
  box-sizing:border-box
}
button{
  border:0;
  border-radius:8px;
  font-weight:700;
  cursor:pointer
}
button:disabled{
  opacity:.5;
  cursor:not-allowed
}
.primary{background:#172a3b;color:#fff}
.secondary{background:#eaf0f4;color:#17212b}
.success{background:#177d4d;color:#fff}
.actions{
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  margin:18px 0
}
.actions button{width:auto}
.hidden{display:none}
.box{
  margin-top:16px;
  padding:12px;
  border-radius:8px;
  background:#edf3f7
}
.error{background:#fff0f0;color:#922}
.warn{background:#fff8e6;color:#725300}
.summary{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:10px;
  margin:18px 0
}
.metric{
  background:#f6f8fa;
  padding:12px;
  border-radius:8px
}
table{
  width:100%;
  border-collapse:collapse;
  font-size:13px
}
th,td{
  padding:8px;
  border-bottom:1px solid #ddd;
  text-align:left;
  vertical-align:top
}
.saved{color:#177d4d;font-weight:700}
.failed{color:#a11;font-weight:700}
.skipped{color:#666}
a{color:#0d6092;font-weight:700;text-decoration:none}

@media(max-width:800px){
  .grid{grid-template-columns:1fr}
  .summary{grid-template-columns:1fr 1fr}
  table{display:block;overflow-x:auto}
}
</style>
</head>

<body>
<main>
<div class="card">
  <h1>HKEX Filing Downloader</h1>
  <p>
    先搜尋 HKEX 文件，再選擇本機 parent folder。
    系統會建立指定子資料夾並逐份儲存 PDF。
  </p>

  <div class="grid">
    <div>
      <label for="stock">股票號碼</label>
      <input id="stock" value="0066">
    </div>

    <div>
      <label for="years">搜尋年期</label>
      <select id="years">
        <option value="5">5</option>
        <option value="6" selected>6</option>
        <option value="7">7</option>
        <option value="10">10</option>
      </select>
    </div>

    <div>
      <label for="folderName">資料夾名稱</label>
      <input id="folderName" value="0066">
    </div>
  </div>

  <div class="actions">
    <button id="searchBtn" class="primary">搜尋 HKEX 文件</button>
    <button id="chooseBtn" class="secondary" disabled>選擇儲存位置</button>
    <button id="downloadBtn" class="success" disabled>下載已選文件</button>
  </div>

  <div id="folderStatus" class="box hidden"></div>
  <div id="statusBox" class="box hidden"></div>
  <div id="errorBox" class="box error hidden"></div>
  <div id="warnBox" class="box warn hidden"></div>

  <section id="results" class="hidden">
    <h2 id="issuer"></h2>

    <div class="summary">
      <div class="metric">找到<br><b id="found">0</b></div>
      <div class="metric">已選<br><b id="selected">0</b></div>
      <div class="metric">已儲存<br><b id="saved">0</b></div>
      <div class="metric">失敗<br><b id="failed">0</b></div>
    </div>

    <div class="actions">
      <button id="allBtn" class="secondary">Select All</button>
      <button id="noneBtn" class="secondary">Deselect All</button>

      <label style="margin-left:auto">
        已存在檔案：
        <select id="existingMode" style="width:auto">
          <option value="skip" selected>Skip</option>
          <option value="replace">Replace</option>
          <option value="rename">Rename</option>
        </select>
      </label>
    </div>

    <table>
      <thead>
        <tr>
          <th></th>
          <th>日期</th>
          <th>類型</th>
          <th>公告</th>
          <th>狀態</th>
          <th>HKEX</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </section>
</div>
</main>

<script>
"use strict";

let documents = [];
let parentDirectoryHandle = null;
let targetDirectoryHandle = null;
let folderNameTouched = false;

const byId = (id) => document.getElementById(id);
const show = (el) => el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

function safeFilename(value) {
  const forbidden = new Set(["<", ">", ":", "\"", "/", "\\\\", "|", "?", "*"]);
  let out = "";

  for (const ch of String(value || "untitled")) {
    const code = ch.charCodeAt(0);

    if (code < 32 || forbidden.has(ch)) {
      out += "_";
    } else {
      out += ch;
    }
  }

  out = out.trim();

  while (out.includes("  ")) {
    out = out.replace("  ", " ");
  }

  if (!out) out = "untitled";

  return out.slice(0, 120);
}

function updateSelectedCount() {
  const count = document.querySelectorAll(".doc-check:checked").length;
  byId("selected").textContent = String(count);
  byId("downloadBtn").disabled = !(count > 0 && targetDirectoryHandle);
}

function setRowStatus(index, text, className) {
  const el = byId(`status-${index}`);
  if (!el) return;
  el.textContent = text;
  el.className = className || "";
}

function renderDocuments() {
  const tbody = byId("rows");
  tbody.innerHTML = "";

  documents.forEach((doc, index) => {
    const tr = document.createElement("tr");

    const selectTd = document.createElement("td");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.className = "doc-check";
    checkbox.dataset.index = String(index);
    checkbox.addEventListener("change", updateSelectedCount);
    selectTd.appendChild(checkbox);

    const dateTd = document.createElement("td");
    dateTd.textContent = doc.publication_date || "";

    const typeTd = document.createElement("td");
    typeTd.textContent = doc.document_type || "";

    const titleTd = document.createElement("td");
    titleTd.textContent = doc.title || "";

    const statusTd = document.createElement("td");
    statusTd.id = `status-${index}`;
    statusTd.textContent = "Ready";

    const linkTd = document.createElement("td");
    const link = document.createElement("a");
    link.href = doc.source_url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Open PDF";
    linkTd.appendChild(link);

    tr.append(selectTd, dateTd, typeTd, titleTd, statusTd, linkTd);
    tbody.appendChild(tr);
  });

  byId("found").textContent = String(documents.length);
  byId("saved").textContent = "0";
  byId("failed").textContent = "0";
  updateSelectedCount();
}

byId("stock").addEventListener("input", () => {
  if (!folderNameTouched) {
    byId("folderName").value = byId("stock").value.trim();
  }
});

byId("folderName").addEventListener("input", () => {
  folderNameTouched = true;
});

byId("searchBtn").addEventListener("click", async () => {
  hide(byId("errorBox"));
  hide(byId("warnBox"));
  hide(byId("results"));
  show(byId("statusBox"));

  byId("statusBox").textContent = "正在搜尋 HKEX 文件…";
  byId("searchBtn").disabled = true;

  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        stock: byId("stock").value.trim(),
        years: Number(byId("years").value)
      })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Search failed");
    }

    documents = data.documents || [];

    byId("issuer").textContent =
      `${data.stock_code || ""} — ${data.company || ""}`;

    if (!folderNameTouched) {
      byId("folderName").value =
        byId("stock").value.trim() || data.stock_code || "HKEX";
    }

    renderDocuments();

    hide(byId("statusBox"));
    show(byId("results"));
    byId("chooseBtn").disabled = false;

    if (!("showDirectoryPicker" in window)) {
      show(byId("warnBox"));
      byId("warnBox").textContent =
        "此瀏覽器不支援本機資料夾寫入。請使用最新版 Chrome 或 Edge。";
      byId("chooseBtn").disabled = true;
    }

  } catch (error) {
    hide(byId("statusBox"));
    show(byId("errorBox"));
    byId("errorBox").textContent =
      error && error.message ? error.message : String(error);

  } finally {
    byId("searchBtn").disabled = false;
  }
});

byId("chooseBtn").addEventListener("click", async () => {
  hide(byId("errorBox"));

  try {
    parentDirectoryHandle = await window.showDirectoryPicker({
      mode: "readwrite",
      startIn: "downloads"
    });

    const childFolderName = safeFilename(
      byId("folderName").value || byId("stock").value || "HKEX"
    );

    targetDirectoryHandle =
      await parentDirectoryHandle.getDirectoryHandle(
        childFolderName,
        {create: true}
      );

    show(byId("folderStatus"));

    byId("folderStatus").textContent =
      `已選 parent folder：${parentDirectoryHandle.name}；`
      + `子資料夾：${targetDirectoryHandle.name}`;

    updateSelectedCount();

  } catch (error) {
    if (error && error.name === "AbortError") return;

    show(byId("errorBox"));
    byId("errorBox").textContent =
      "選擇資料夾失敗："
      + (error && error.message ? error.message : String(error));
  }
});

byId("allBtn").addEventListener("click", () => {
  document.querySelectorAll(".doc-check")
    .forEach((el) => el.checked = true);
  updateSelectedCount();
});

byId("noneBtn").addEventListener("click", () => {
  document.querySelectorAll(".doc-check")
    .forEach((el) => el.checked = false);
  updateSelectedCount();
});

async function fileExists(dirHandle, filename) {
  try {
    await dirHandle.getFileHandle(filename);
    return true;
  } catch (error) {
    if (error && error.name === "NotFoundError") {
      return false;
    }
    throw error;
  }
}

async function renamedFilename(dirHandle, filename) {
  const dot = filename.lastIndexOf(".");
  const base = dot > 0 ? filename.slice(0, dot) : filename;
  const ext = dot > 0 ? filename.slice(dot) : "";

  let number = 2;
  let candidate = filename;

  while (await fileExists(dirHandle, candidate)) {
    candidate = `${base}_${number}${ext}`;
    number += 1;
  }

  return candidate;
}

async function saveBlob(dirHandle, filename, blob) {
  const fileHandle =
    await dirHandle.getFileHandle(filename, {create: true});

  const writable = await fileHandle.createWritable();
  await writable.write(blob);
  await writable.close();
}

byId("downloadBtn").addEventListener("click", async () => {
  hide(byId("errorBox"));
  hide(byId("warnBox"));

  if (!targetDirectoryHandle) {
    show(byId("errorBox"));
    byId("errorBox").textContent = "請先選擇儲存位置。";
    return;
  }

  const selectedIndexes =
    [...document.querySelectorAll(".doc-check:checked")]
      .map((el) => Number(el.dataset.index));

  if (!selectedIndexes.length) return;

  const mode = byId("existingMode").value;
  let savedCount = 0;
  let failedCount = 0;

  byId("downloadBtn").disabled = true;

  for (const index of selectedIndexes) {
    const doc = documents[index];

    let filename = safeFilename(
      `${doc.stock_code || byId("stock").value}_`
      + `${doc.publication_date || "unknown-date"}_`
      + `${doc.title || "filing"}.pdf`
    );

    setRowStatus(index, "Downloading…", "");

    try {
      const exists = await fileExists(targetDirectoryHandle, filename);

      if (exists && mode === "skip") {
        setRowStatus(index, "Skipped (exists)", "skipped");
        continue;
      }

      if (exists && mode === "rename") {
        filename =
          await renamedFilename(targetDirectoryHandle, filename);
      }

      const response = await fetch(doc.source_url, {
        method: "GET",
        mode: "cors",
        credentials: "omit"
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const fileBlob = await response.blob();

      if (fileBlob.size < 100) {
        throw new Error("Downloaded file is unexpectedly small.");
      }

      await saveBlob(targetDirectoryHandle, filename, fileBlob);

      savedCount += 1;
      setRowStatus(index, "Saved", "saved");

    } catch (error) {
      failedCount += 1;
      setRowStatus(index, "Failed", "failed");

      show(byId("warnBox"));
      byId("warnBox").textContent =
        "若 Open PDF 正常但下載顯示 Failed，通常係 HKEX CORS 阻擋。"
        + "下一版可以加入單文件 download helper。";
    }

    byId("saved").textContent = String(savedCount);
    byId("failed").textContent = String(failedCount);
  }

  byId("downloadBtn").disabled = false;
});
</script>
</body>
</html>
"""
