"""FastAPI REST API for serving scraped job data from S3."""

import json
import os
from time import time

import boto3
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

API_TOKEN = os.environ.get("API_TOKEN", "")
_bearer = HTTPBearer(auto_error=False)


async def _verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    if request.url.path == "/health":
        return
    if not API_TOKEN:
        return
    if not credentials or credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
        )


app = FastAPI(
    title="Career Scraper API",
    version="0.1.0",
    dependencies=[Depends(_verify_token)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dashboard.aloysjehwin.com",
        "http://localhost:3000",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)

S3_BUCKET = os.environ.get("JOBS_S3_BUCKET", "dashboard-static-assets-708835965056")
S3_REGION = os.environ.get("AWS_REGION", "us-east-1")
CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "300"))
VALID_COMPANIES = [
    "microsoft", "google", "amazon", "apple", "meta",
    "sap", "oracle", "visa", "salesforce",
]

_cache: dict[str, tuple[float, dict]] = {}
_s3 = None


def _get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=S3_REGION)
    return _s3


def _get_from_s3(company: str) -> dict | None:
    now = time()
    if company in _cache and (now - _cache[company][0]) < CACHE_TTL:
        return _cache[company][1]

    try:
        resp = _get_s3().get_object(
            Bucket=S3_BUCKET,
            Key=f"jobs/{company}-latest.json",
        )
        data = json.loads(resp["Body"].read().decode())
        _cache[company] = (now, data)
        return data
    except Exception:
        return None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/companies")
def list_companies():
    return {"companies": VALID_COMPANIES}


@app.get("/jobs")
def list_all_jobs():
    result = {}
    for company in VALID_COMPANIES:
        data = _get_from_s3(company)
        if data:
            result[company] = data
    return {"companies": result}


@app.get("/jobs/{company}")
def get_company_jobs(company: str):
    if company not in VALID_COMPANIES:
        raise HTTPException(404, f"Unknown company: {company}")
    data = _get_from_s3(company)
    if not data:
        raise HTTPException(404, f"No data available for {company}")
    return data


def main():
    import uvicorn

    uvicorn.run(
        "career_scraper.api:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
