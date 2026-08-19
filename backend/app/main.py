from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, auth, chat, superchat_webhook

app = FastAPI(title="LUCE — Tutor AI Accademia Coppola")

app.add_middleware(
    CORSMiddleware,
    # FRONTEND_ORIGIN in produzione (es. https://luce.vercel.app), "*" solo in sviluppo.
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(superchat_webhook.router)


@app.get("/health")
def health():
    return {"status": "ok"}
