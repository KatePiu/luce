-- Schema LUCE — tutor AI Accademia Coppola
-- Vedi documento di architettura per la descrizione di ogni tabella.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- per gen_random_uuid()

CREATE TABLE IF NOT EXISTS techniques (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- tassonomia a 5 categorie: 'taglio', 'piega', 'tecnico' (colorazione — include
    -- anche Shatush e Infusion), 'altri_prodotti', 'casi_particolari'.
    slug TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Un video guida, indipendente dai file di supporto (trascrizione/timestamp):
-- può esistere anche da solo, con il solo titolo, se non c'è ancora una
-- trascrizione — l'agente potrà comunque proporne il link. La piattaforma è
-- esplicita (oggi Drive, in futuro Vimeo o altro) così cambiarla non tocca
-- la logica dell'agente, solo questo record.
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'drive' CHECK (platform IN ('drive', 'vimeo', 'youtube', 'other')),
    url TEXT NOT NULL,
    technique_id UUID REFERENCES techniques(id),
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_videos_technique ON videos(technique_id);

CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    technique_id UUID REFERENCES techniques(id),
    video_id UUID REFERENCES videos(id) ON DELETE SET NULL,  -- video a cui questa fonte si riferisce (trascrizione o guida discorsiva dello stesso video)
    document_url TEXT,                  -- link al documento originale (Drive)
    origin_filename TEXT NOT NULL,      -- nome del file caricato
    origin_kind TEXT NOT NULL CHECK (origin_kind IN ('transcript_csv', 'guide_doc', 'product_sheet', 'case_table', 'other')),
    version INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 0,     -- priorità in caso di fonti multiple sullo stesso argomento
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    checksum TEXT,                       -- hash del contenuto, per capire se un file è cambiato
    uploaded_by UUID,                    -- FK verso users, nullable per import iniziali
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sources_technique ON sources(technique_id);
CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status);

-- Migrazione da versioni precedenti dello schema (colonne rimosse/aggiunte):
-- innocuo su un'installazione nuova, dove "sources" viene già creata nella forma finale.
-- Deve stare PRIMA dell'indice su video_id: su un'installazione esistente la
-- colonna non c'è finché questa ALTER non viene eseguita.
ALTER TABLE sources DROP COLUMN IF EXISTS video_title;
ALTER TABLE sources DROP COLUMN IF EXISTS video_url;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS video_id UUID REFERENCES videos(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_sources_video ON sources(video_id);

-- Dimensione dell'embedding: 1024 (voyage-3 / voyage-multilingual-2).
-- Se si cambia provider di embedding con dimensione diversa, aggiornare qui.
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,                -- ordine del chunk all'interno della fonte
    text TEXT NOT NULL,
    start_timestamp TEXT,                -- 'HH:MM:SS' quando disponibile (da trascrizione)
    end_timestamp TEXT,
    embedding VECTOR(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'staff' CHECK (role IN ('staff', 'admin', 'human_tutor')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    channel TEXT NOT NULL CHECK (channel IN ('web', 'whatsapp')),
    external_conversation_id TEXT,       -- id conversazione lato Superchat, per WhatsApp
    external_contact_id TEXT,
    status TEXT NOT NULL DEFAULT 'bot' CHECK (status IN ('bot', 'escalated', 'human_active', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_external ON conversations(external_conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    kind TEXT NOT NULL DEFAULT 'text' CHECK (kind IN ('text', 'voice')),
    body TEXT,
    voice_transcript TEXT,
    voice_audio_url TEXT,
    retrieval_score REAL,                -- punteggio di affidabilità del recupero, se applicabile
    sources_cited JSONB,                 -- elenco {source_id, title, video_url, timestamp} citati nella risposta
    external_message_id TEXT,            -- id Superchat, per idempotenza webhook
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_external_dedup ON messages(external_message_id) WHERE external_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);

-- Scheda diagnostica strutturata (Specifica_Definitiva_Tutor_AI, tabella 2 "Scheda
-- diagnostica standard"): un caso per conversazione, aggiornato dopo ogni risposta del
-- tutor AI da una chiamata di estrazione dedicata (vedi app/rag/case_extraction.py) — non
-- inferita una volta sola, ma tenuta aggiornata via via che la diagnosi procede.
CREATE TABLE IF NOT EXISTS cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    area TEXT,
    tecnica TEXT,
    base_partenza TEXT,
    capelli_bianchi TEXT,
    storico_tecnico TEXT,
    porosita TEXT,
    servizio_eseguito TEXT,
    formula_prodotti TEXT,
    tempi_condizioni TEXT,
    problema_osservato TEXT,
    zona_coinvolta TEXT,
    risultato_desiderato TEXT,
    risultato_reale TEXT,
    fonti_trovate JSONB,
    livello_confidenza TEXT,
    esito TEXT,
    -- macchina a stati del caso, Specifica_Definitiva_Tutor_AI punto 12/22.
    stato TEXT NOT NULL DEFAULT 'RISPOSTA_AI' CHECK (stato IN (
        'RISPOSTA_AI', 'IN_ATTESA_DI_FEEDBACK', 'RISOLTO_DA_AI', 'ESCALATION_TUTOR',
        'RISOLTO_DA_TUTOR', 'NON_RISOLTO', 'DA_VALIDARE', 'VALIDATO_PER_KNOWLEDGE'
    )),
    validated_by UUID REFERENCES users(id),
    validated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cases_stato ON cases(stato);

CREATE TABLE IF NOT EXISTS escalations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    reason TEXT NOT NULL CHECK (reason IN (
        'no_sources', 'insufficient_sources', 'conflicting_sources',
        'missing_info', 'non_standard_case', 'source_requires_human',
        'user_requested', 'repeated_failed_attempts'
    )),
    summary TEXT,
    sources_consulted JSONB,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved')),
    resolved_by UUID REFERENCES users(id),
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

-- Fotografia della scheda diagnostica al momento dell'escalation (tabella 3 del
-- documento): resta leggibile dal tutor umano anche se il caso evolve dopo.
ALTER TABLE escalations ADD COLUMN IF NOT EXISTS case_snapshot JSONB;

CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);

-- Sistema di feedback (Specifica_Definitiva_Tutor_AI, punto 11): un feedback per
-- messaggio outbound del tutor AI. Il "tipo" determina la transizione di stato del caso
-- collegato — vedi app/case_service.py.
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN (
        'mi_e_stata_utile', 'non_ha_risolto_il_problema', 'problema_risolto',
        'problema_parzialmente_risolto', 'problema_non_risolto', 'risposta_non_corretta',
        'ho_dovuto_contattare_il_tutor'
    )),
    nota TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedback_message ON feedback(message_id);
CREATE INDEX IF NOT EXISTS idx_feedback_case ON feedback(case_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID REFERENCES users(id),
    action TEXT NOT NULL,               -- es. 'source.upload', 'source.disable', 'escalation.resolve'
    entity_type TEXT,
    entity_id UUID,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor_id);
