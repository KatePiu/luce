import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import admin, auth, chat, superchat_webhook

logger = logging.getLogger(__name__)

app = FastAPI(title="LUCE — Tutor AI Accademia Coppola")

app.add_middleware(
    CORSMiddleware,
    # FRONTEND_ORIGIN in produzione (uno o più indirizzi separati da virgola), "*" solo in sviluppo.
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Un'eccezione non gestita che risale fino a qui, se lasciata propagare, produce una
    # risposta 500 generata al di fuori del CORSMiddleware (senza header CORS): il browser
    # la segnala al frontend come un generico errore di rete ("Failed to fetch") invece di un
    # messaggio leggibile. Intercettarla qui la fa rientrare nel normale ciclo di risposta.
    logger.exception("Errore non gestito su %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Si è verificato un errore imprevisto. Riprova tra poco."})


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(superchat_webhook.router)


@app.get("/health")
def health():
    return {"status": "ok"}
