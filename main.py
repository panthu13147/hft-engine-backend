import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text

app = FastAPI()

# 🛡️ Bulletproof CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 📦 Data Structure Definition
class ContactForm(BaseModel):
    name: str
    email: str
    message: str


# 🔗 VAULT CONNECTION: Render se Secret Key uthana
DB_URL = os.getenv("DATABASE_URL")

engine = None
if DB_URL:
    try:
        engine = create_engine(DB_URL)
        print("✅ DATABASE ENGINE INITIALIZED", flush=True)
    except Exception as e:
        print(f"❌ DATABASE INIT ERROR: {e}", flush=True)


@app.get("/")
async def root():
    return {
        "status": "HFT Engine Online",
        "vault_connected": engine is not None
    }


# 📨 THE COMMS CHANNEL (With Memory)
@app.post("/contact")
async def receive_contact(form_data: ContactForm):
    print("\n" + "=" * 50, flush=True)
    print("🚨 INCOMING TRANSMISSION FROM FRONTEND 🚨", flush=True)
    print(f"👤 Sender: {form_data.name}", flush=True)
    print(f"📧 Email: {form_data.email}", flush=True)
    print(f"💬 Message: {form_data.message}", flush=True)
    print("=" * 50 + "\n", flush=True)

    # 💾 DATA KO PERMANENTLY SUPABASE MEIN LOCK KARNA
    if engine:
        try:
            with engine.connect() as conn:
                query = text("""
                             INSERT INTO contact_messages (sender_name, sender_email, message)
                             VALUES (:name, :email, :message)
                             """)
                conn.execute(query, {"name": form_data.name, "email": form_data.email, "message": form_data.message})
                conn.commit()
            print("🔐 DATA SUCCESSFULLY LOCKED IN SUPABASE VAULT", flush=True)
        except Exception as e:
            print(f"❌ VAULT WRITE ERROR: {e}", flush=True)
            return {"status": "error", "message": "Failed to save transmission."}

    return {"status": "success", "message": "Transmission received and locked in the vault."}