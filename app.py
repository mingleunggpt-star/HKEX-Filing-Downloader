from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from hkex_search import search_filings

app = FastAPI(title="HKEX Filing Downloader v4.3")

# Replace this after deploying the Cloudflare Worker.
# Example: https://hkex-pdf-proxy.your-subdomain.workers.dev
WORKER_BASE_URL = "https://hkex-pdf-proxy.mingleunggpt.workers.dev"


class SearchRequest(BaseModel):
    stock: str = Field(min_length=1, max_length=12)
    years: int = Field(default=6, ge=1, le=15)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "service": "hkex-filing-downloader",
        "version": "4.3.0"
    }


@app.post("/api/search")
async def search(req: SearchRequest):
    try:
        return await search_filings(req.stock, req.years)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_PAGE.replace("__WORKER_BASE_URL__", WORKER_BASE_URL)


HTML_PAGE = r"""
<!doctype html>
<html lang="zh-HK">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HKEX Filing Downloader v4.1</title>

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
    <button id="retryBtn" class="secondary" disabled>Retry Failed</button>
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

const WORKER_BASE_URL = "__WORKER_BASE_URL__";

let documents = [];
let parentDirectoryHandle = null;
let targetDirectoryHandle = null;
let folderNameTouched = false;
let failedIndexes = new Set();

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

  if (className === "failed") {
    failedIndexes.add(index);
  } else if (className === "saved" || className === "skipped") {
    failedIndexes.delete(index);
  }

  byId("retryBtn").disabled = failedIndexes.size === 0 || !targetDirectoryHandle;
}

function renderDocuments() {
  failedIndexes = new Set();
  byId("retryBtn").disabled = true;
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

    if (parentDirectoryHandle.name === childFolderName) {
      targetDirectoryHandle = parentDirectoryHandle;
    } else {
      targetDirectoryHandle =
        await parentDirectoryHandle.getDirectoryHandle(
          childFolderName,
          {create: true}
        );
    }

    show(byId("folderStatus"));

    byId("folderStatus").textContent =
      targetDirectoryHandle === parentDirectoryHandle
        ? `已選資料夾：${targetDirectoryHandle.name}（直接儲存，不再建立同名子資料夾）`
        : `已選 parent folder：${parentDirectoryHandle.name}；子資料夾：${targetDirectoryHandle.name}`;

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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "?";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;

  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }

  const digits = unit === 0 ? 0 : 1;
  return `${value.toFixed(digits)} ${units[unit]}`;
}

function parseContentRange(value) {
  // Example: bytes 0-0/12345678
  const match = /^bytes\s+(\d+)-(\d+)\/(\d+|\*)$/i.exec(
    String(value || "").trim()
  );

  if (!match) return null;

  return {
    start: Number(match[1]),
    end: Number(match[2]),
    total: match[3] === "*" ? null : Number(match[3])
  };
}

function proxyUrlFor(doc) {
  return `${WORKER_BASE_URL}/?url=${encodeURIComponent(doc.source_url)}`;
}

async function fetchRangeWithRetry(
  doc,
  start,
  end,
  maxRetries = 2
) {
  let lastError = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(
        `${proxyUrlFor(doc)}&chunk_attempt=${attempt + 1}`,
        {
          method: "GET",
          headers: {
            "Range": `bytes=${start}-${end}`
          },
          cache: "no-store"
        }
      );

      const upstreamStatus =
        response.headers.get("x-hkex-upstream-status") || "";
      const upstreamType =
        response.headers.get("x-hkex-upstream-content-type") || "";
      const contentRange =
        response.headers.get("content-range") || "";

      if (!response.ok) {
        let detail = "";

        try {
          const errorData = await response.json();
          detail =
            errorData.error ||
            errorData.upstream_content_type ||
            JSON.stringify(errorData).slice(0, 250);
        } catch (_) {
          try {
            detail = (await response.text()).slice(0, 250);
          } catch (_) {}
        }

        throw new Error(
          `HTTP ${response.status}`
          + (upstreamStatus ? ` / HKEX ${upstreamStatus}` : "")
          + (upstreamType ? ` / ${upstreamType}` : "")
          + (detail ? ` / ${detail}` : "")
        );
      }

      if (response.status !== 206) {
        throw new Error(
          `Range unsupported: expected 206, got ${response.status}`
          + (contentRange ? ` / ${contentRange}` : "")
        );
      }

      const parsed = parseContentRange(contentRange);

      if (!parsed) {
        throw new Error(
          `Missing/invalid Content-Range: ${contentRange || "none"}`
        );
      }

      if (parsed.start !== start) {
        throw new Error(
          `Unexpected range start ${parsed.start}, expected ${start}`
        );
      }

      const buffer = await response.arrayBuffer();
      const expectedLength = parsed.end - parsed.start + 1;

      if (buffer.byteLength !== expectedLength) {
        throw new Error(
          `Chunk size mismatch: got ${buffer.byteLength}, expected ${expectedLength}`
        );
      }

      return {
        buffer,
        range: parsed,
        contentType:
          response.headers.get("content-type") || ""
      };

    } catch (error) {
      lastError = error;

      if (attempt < maxRetries) {
        await sleep(800 * (attempt + 1));
      }
    }
  }

  throw lastError || new Error("Chunk download failed after retries");
}

async function discoverFileSize(doc) {
  // Ask for one byte only. A compliant Range response tells us
  // the complete file size in Content-Range: bytes 0-0/TOTAL.
  const probe = await fetchRangeWithRetry(doc, 0, 0, 2);

  if (
    !probe.range ||
    !Number.isFinite(probe.range.total) ||
    probe.range.total <= 0
  ) {
    throw new Error("Unable to determine PDF size from Content-Range");
  }

  return probe.range.total;
}

async function openWritableFile(filename) {
  const fileHandle =
    await targetDirectoryHandle.getFileHandle(
      filename,
      {create: true}
    );

  // createWritable() truncates/replaces the target when committed.
  return await fileHandle.createWritable();
}

async function downloadPdfChunked(
  doc,
  filename,
  rowIndex
) {
  const CHUNK_SIZE = 4 * 1024 * 1024;

  const totalSize = await discoverFileSize(doc);

  const writable = await openWritableFile(filename);

  let written = 0;

  try {
    while (written < totalSize) {
      const end = Math.min(
        written + CHUNK_SIZE - 1,
        totalSize - 1
      );

      const result = await fetchRangeWithRetry(
        doc,
        written,
        end,
        2
      );

      await writable.write({
        type: "write",
        position: written,
        data: result.buffer
      });

      written += result.buffer.byteLength;

      const percent = Math.min(
        100,
        Math.floor((written / totalSize) * 100)
      );

      setRowStatus(
        rowIndex,
        `${percent}% · ${formatBytes(written)} / ${formatBytes(totalSize)}`,
        "downloading"
      );
    }

    if (written !== totalSize) {
      throw new Error(
        `Final size mismatch: wrote ${written}, expected ${totalSize}`
      );
    }

    await writable.close();

    return {
      totalSize,
      written
    };

  } catch (error) {
    try {
      await writable.abort();
    } catch (_) {}

    throw error;
  }
}

async function downloadIndexes(indexes) {
  if (WORKER_BASE_URL.includes("REPLACE-ME")) {
    show(byId("errorBox"));
    byId("errorBox").textContent =
      "尚未設定 Cloudflare Worker URL。";
    return;
  }

  if (!targetDirectoryHandle) {
    show(byId("errorBox"));
    byId("errorBox").textContent =
      "請先選擇儲存位置。";
    return;
  }

  if (!indexes.length) return;

  const mode = byId("existingMode").value;

  let savedCount =
    Number(byId("saved").textContent || "0");

  let failedCount =
    Number(byId("failed").textContent || "0");

  byId("downloadBtn").disabled = true;
  byId("retryBtn").disabled = true;

  for (const index of indexes) {
    const doc = documents[index];

    let filename = safeFilename(
      `${doc.stock_code || byId("stock").value}_`
      + `${doc.publication_date || "unknown-date"}_`
      + `${doc.title || "filing"}.pdf`
    );

    setRowStatus(
      index,
      "Preparing chunks…",
      "downloading"
    );

    try {
      const alreadyExists =
        await fileExists(
          targetDirectoryHandle,
          filename
        );

      if (
        alreadyExists &&
        mode === "skip"
      ) {
        setRowStatus(
          index,
          "Skipped (exists)",
          "skipped"
        );
        continue;
      }

      if (
        alreadyExists &&
        mode === "rename"
      ) {
        filename =
          await renamedFilename(
            targetDirectoryHandle,
            filename
          );
      }

      const wasPreviouslyFailed =
        failedIndexes.has(index);

      const result =
        await downloadPdfChunked(
          doc,
          filename,
          index
        );

      savedCount += 1;

      if (
        wasPreviouslyFailed &&
        failedCount > 0
      ) {
        failedCount -= 1;
      }

      setRowStatus(
        index,
        `Saved · ${formatBytes(result.written)}`,
        "saved"
      );

    } catch (error) {
      const wasAlreadyFailed =
        failedIndexes.has(index);

      if (!wasAlreadyFailed) {
        failedCount += 1;
      }

      const message =
        error && error.message
          ? error.message
          : String(error);

      setRowStatus(
        index,
        `Failed: ${message.slice(0, 130)}`,
        "failed"
      );

      show(byId("warnBox"));

      byId("warnBox").textContent =
        "部分文件分段下載失敗。"
        + "每個 4 MB chunk 已自動 retry；"
        + "可按 Retry Failed 只重試失敗文件。";
    }

    byId("saved").textContent =
      String(savedCount);

    byId("failed").textContent =
      String(failedCount);
  }

  updateSelectedCount();

  byId("retryBtn").disabled =
    failedIndexes.size === 0 ||
    !targetDirectoryHandle;
}

byId("downloadBtn").addEventListener("click", async () => {
  hide(byId("errorBox"));
  hide(byId("warnBox"));

  const selectedIndexes =
    [...document.querySelectorAll(".doc-check:checked")]
      .map((el) => Number(el.dataset.index));

  await downloadIndexes(selectedIndexes);
});

byId("retryBtn").addEventListener("click", async () => {
  hide(byId("errorBox"));
  hide(byId("warnBox"));

  const indexes = [...failedIndexes];
  await downloadIndexes(indexes);
});

</script>
</body>
</html>
"""
