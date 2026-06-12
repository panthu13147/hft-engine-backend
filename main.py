import os
import random
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# ── Logging (replaces print statements) ──────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ── Database Engine (with proper connection pooling) ──────────────────────────
# pool_pre_ping: tests connection before using it (avoids stale conn errors)
# pool_recycle:  recycles connections every 5 min (Render kills idle DB conns)
# pool_size:     max 5 persistent connections (free tier safe)
# max_overflow:  up to 5 extra burst connections
DB_URL = os.getenv("DATABASE_URL")
engine = None

if DB_URL:
    try:
        engine = create_engine(
            DB_URL,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=5,
            pool_recycle=300,
            pool_pre_ping=True,
        )
        log.info("✅ DATABASE ENGINE INITIALIZED")
    except Exception as e:
        log.error(f"❌ DATABASE INIT ERROR: {e}")

# ── App Lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 HFT Engine starting up...")
    yield
    log.info("🛑 HFT Engine shutting down...")
    if engine:
        engine.dispose()

app = FastAPI(lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────────────
# In prod, restrict to your actual domain; keep ["*"] only for local dev
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://panthu13147.me,https://www.panthu13147.me,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Simple in-memory rate limiter (IP-based, resets on restart) ───────────────
from collections import defaultdict
import time

_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 5      # max 5 contact submissions
RATE_WINDOW = 3600  # per hour per IP

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    timestamps = _rate_store[ip]
    # Remove timestamps outside the window
    _rate_store[ip] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        return True
    _rate_store[ip].append(now)
    return False

# ── Data Models ───────────────────────────────────────────────────────────────
class ContactForm(BaseModel):
    name: str
    email: EmailStr      # validates email format automatically
    message: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        if len(v) > 100:
            raise ValueError("Name must be under 100 characters")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Message must be at least 5 characters")
        if len(v) > 2000:
            raise ValueError("Message must be under 2000 characters")
        return v

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "status": "HFT Engine Online",
        "vault_connected": engine is not None,
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/health")
async def health():
    db_ok = False
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.post("/contact", status_code=201)
async def receive_contact(form_data: ContactForm, request: Request):
    # Rate limit check
    client_ip = request.headers.get("X-Forwarded-For", request.client.host or "unknown")
    if is_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Try again in an hour.")

    log.info(f"📨 Contact from {form_data.name} <{form_data.email}>")

    if not engine:
        log.warning("⚠️ DB not connected — message not persisted")
        # Still return success so the user isn't confused (log it on your end)
        return {"status": "success", "message": "Transmission received."}

    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO contact_messages (sender_name, sender_email, message)
                    VALUES (:name, :email, :message)
                """),
                {"name": form_data.name, "email": form_data.email, "message": form_data.message},
            )
            conn.commit()
        log.info(f"✅ Saved to DB — {form_data.email}")
    except Exception as e:
        log.error(f"❌ DB WRITE ERROR: {e}")
        raise HTTPException(status_code=500, detail="Failed to save message. Please try again.")

    return {"status": "success", "message": "Transmission received and locked in the vault."}

@app.get("/ticker")
async def live_ticker():
    # Simulated HFT micro-fluctuations
    # NOTE: These are fake prices for portfolio demo purposes
    btc_price = 64230.50 + random.uniform(-25.0, 25.0)
    sol_price = 145.20 + random.uniform(-1.5, 1.5)
    return {
        "BTC": round(btc_price, 2),
        "SOL": round(sol_price, 2),
        "status": "LIVE_FEED",
    }

# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
