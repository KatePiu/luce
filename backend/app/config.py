from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://luce:luce@localhost:5432/luce"

    # Anthropic (generazione risposte)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # Voyage AI (embeddings per la ricerca semantica)
    voyage_api_key: str = ""
    voyage_model: str = "voyage-multilingual-2"

    # Trascrizione vocale (STT) - client OpenAI-compatibile
    stt_api_key: str = ""
    stt_api_base: str = "https://api.openai.com/v1"
    stt_model: str = "whisper-1"

    # Superchat (WhatsApp)
    superchat_api_key: str = ""
    superchat_api_base: str = "https://api.superchat.com/v1.0"
    superchat_webhook_secret: str = ""
    superchat_channel_id: str = ""
    superchat_human_agent_user_id: str = ""  # id utente Superchat del tutor umano, per assigned_users

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    # Escalation
    human_tutor_email: str = "nicola.ratti@katepiu.com"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "luce@katepiu.com"

    # RAG
    retrieval_top_k: int = 6
    retrieval_min_score: float = 0.55  # soglia minima di affidabilità (cosine similarity 0-1)
    chunk_target_chars: int = 900
    chunk_overlap_chars: int = 150

    # Ambiente
    environment: str = "development"
    frontend_origin: str = "*"  # es. https://luce.vercel.app — restringere in produzione


settings = Settings()
