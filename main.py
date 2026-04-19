from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel  # 👈 Yeh naya tool import kiya

app = FastAPI()

# 🛡️ CORS Middleware (Next.js ko allow karne ke liye)
# 🛡️ CORS Middleware (Bulletproof Configuration)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 👈 Isko "*" kar diya taaki sab allow ho
    allow_credentials=False, # 👈 Isko False karna zaroori hai "*" ke sath
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📦 Data Structure Definition (Security Guard)
class ContactForm(BaseModel):
    name: str
    email: str
    message: str


@app.get("/")
async def root():
    return {"status": "HFT Engine Online"}


# 📨 THE COMMS CHANNEL: Naya POST route banaya
# 📨 THE COMMS CHANNEL:
@app.post("/contact")
async def receive_contact(form_data: ContactForm):
    # flush=True is REQUIRED in the cloud to bypass Python's lazy buffering
    print("\n" + "=" * 50, flush=True)
    print("🚨 INCOMING TRANSMISSION FROM FRONTEND 🚨", flush=True)
    print(f"👤 Sender: {form_data.name}", flush=True)
    print(f"📧 Email: {form_data.email}", flush=True)
    print(f"💬 Message: {form_data.message}", flush=True)
    print("=" * 50 + "\n", flush=True)

    return {"status": "success", "message": "Transmission received by Panth's Terminal."}