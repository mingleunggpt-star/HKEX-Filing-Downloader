from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from _hkex_engine import run_download

app = FastAPI(title="HKEX Filing Downloader API")


class DownloadRequest(BaseModel):
    stock: str = Field(min_length=1, max_length=12)
    years: int = Field(default=6, ge=1, le=15)


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "service": "hkex-filing-downloader",
        "version": "3.1"
    }


@app.post("/api/download")
async def download(req: DownloadRequest):
    try:
        return await run_download(req.stock, req.years)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
