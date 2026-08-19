# LUCE — Tutor AI Accademia Coppola

Tutor AI per i parrucchieri Coppola: risponde a domande tecniche in chat web e
WhatsApp, usando solo i materiali approvati dall'Accademia, con citazione di
fonte, video e timestamp, e inoltro a un tutor umano quando i materiali non
bastano.

Questo file è scritto per chi non ha esperienza di sviluppo: segui i passaggi
in ordine. Non serve capire il codice per far partire il progetto.

## Cosa contiene questa cartella

```
LUCE/
  backend/    Il "motore": API, ricerca nei materiali, generazione risposte, WhatsApp
  frontend/   La chat web che useranno i parrucchieri (e il pannello admin)
  data/       Il dataset "casi particolari" già recuperato dal Drive (vedi sotto)
  docker-compose.yml   Avvia database + backend + frontend con un solo comando
  .env.example          Modello del file di configurazione da compilare
```

## Cosa è stato verificato in questa fase

- Il backend si avvia, tutte le rotte sono registrate correttamente, e i test
  automatici passano (`pytest`, 11 test su parsing dei materiali e controlli
  anti-allucinazione).
- Il frontend compila senza errori (`npm run build`), incluse chat, cronologia,
  login e pannello admin.
- **Non è stato possibile fare una prova end-to-end con un database reale** in
  questo ambiente (non è disponibile Docker): schema del database, backend e
  frontend sono stati verificati singolarmente ma non ancora insieme con dati
  reali. Il primo `docker compose up` (sezione 3) è anche il primo collaudo
  completo — se qualcosa non va, fammelo sapere con l'errore esatto.
- L'integrazione Superchat è scritta seguendo la documentazione ufficiale
  verificata il 19/08/2026, ma **non è stata testata con un account reale**
  (non ne esisteva uno attivo al momento della scrittura).

## 1. Cosa ti serve prima di iniziare

- **Docker Desktop** installato e avviato (gratuito): <https://www.docker.com/products/docker-desktop/>
- Le chiavi/credenziali elencate nella sezione 2 (alcune si possono aggiungere
  in un secondo momento — il progetto parte comunque, semplicemente quelle
  funzioni non risponderanno finché non le aggiungi).

## 2. Configurazione (`.env`)

Copia `.env.example` in un nuovo file chiamato `.env` nella stessa cartella, e
compila i valori:

| Voce | A cosa serve | Dove trovarla |
|---|---|---|
| `ANTHROPIC_API_KEY` | Genera le risposte del tutor | console.anthropic.com → API Keys |
| `VOYAGE_API_KEY` | Cerca i passaggi pertinenti nei materiali | console.voyageai.com |
| `STT_API_KEY` | Trascrive i messaggi vocali | Il fornitore scelto per la trascrizione (es. una chiave OpenAI, se usi Whisper) |
| `SUPERCHAT_API_KEY`, `SUPERCHAT_CHANNEL_ID` | Collegano WhatsApp | Dashboard Superchat → Impostazioni → Integrazioni, dopo aver attivato l'account (vedi documento di architettura, sezione 15) |
| `SUPERCHAT_WEBHOOK_SECRET` | Sicurezza del webhook | Restituito da Superchat quando crei la sottoscrizione webhook (vedi `backend/app/integrations/superchat.py`, funzione `create_webhook`) |
| `JWT_SECRET` | Sicurezza degli accessi | Inventane una lunga e casuale, non deve essere "memorabile" |
| `HUMAN_TUTOR_EMAIL` | Chi riceve le escalation | Già impostato su `nicola.ratti@katepiu.com` |
| `SMTP_*` | Invio delle email di escalation | Le credenziali del servizio email che userai (es. Gmail con password per app, SendGrid, ecc.) — se le lasci vuote, le escalation vengono solo scritte nei log del backend invece che inviate via email |

Le voci che lasci vuote non bloccano l'avvio: semplicemente quella funzione
specifica (es. trascrizione vocale) darà errore finché non la compili.

## 3. Avvio in locale

Da questa cartella (`LUCE/`), con Docker Desktop aperto:

```bash
docker compose up --build
```

La prima volta scarica le immagini e crea il database — richiede qualche
minuto. Al termine:

- Backend disponibile su <http://localhost:8000> (documentazione interattiva
  delle API su <http://localhost:8000/docs>)
- Frontend (chat) su <http://localhost:3000>

## 4. Creare il primo utente amministratore

In un altro terminale, con i container ancora avviati:

```bash
docker compose exec backend python -m scripts.create_admin nicola.ratti@katepiu.com "una-password-sicura"
```

Con questo account potrai accedere sia alla chat sia al pannello
amministrazione (visibile dal pulsante "Admin" nella chat).

## 5. Caricare i materiali reali dell'Accademia

Il pannello admin (`/admin` nel frontend, oppure `/docs` sul backend) permette
di caricare i file uno alla volta: file, categoria (Tagli/Pieghe/Tecnico/
Shatush/Infusion/Altri prodotti/Casi particolari), e facoltativamente il link
al video e al documento originale.

Formati supportati, corrispondenti a quelli trovati nella cartella
`_TRASCRIZIONI` del Drive:
- **CSV di trascrizione** (con timestamp) → indicizzato riga per riga, i
  timestamp vengono mostrati nelle risposte del tutor.
- **.docx / .md** (guide, schede prodotto) → indicizzato per paragrafi.
- **Casi_particolari.txt** (una riga = un caso) → un file di esempio reale è
  già in `data/casi_particolari/Casi_particolari.txt`, recuperato durante
  l'analisi: puoi caricarlo subito per iniziare a testare il sistema.

I file con prefisso `._` (residui macOS) vengono rifiutati automaticamente
dall'ingestione: non serve toglierli manualmente dalla cartella prima di
caricarli, ma se provi a caricarne uno per errore il sistema te lo segnala e
non lo indicizza.

Caricare di nuovo un file con lo stesso nome nella stessa categoria lo
aggiorna (nuova versione), senza dover ricostruire tutto l'indice.

## 6. Collegare Superchat (WhatsApp)

1. Attiva l'account Superchat (vedi documento di architettura per il costo da
   verificare separatamente dal budget di €100/mese).
2. Prendi `SUPERCHAT_API_KEY` e `SUPERCHAT_CHANNEL_ID` dalla loro dashboard,
   mettili nel `.env`.
3. Esegui una volta sola (dopo aver esposto il backend su un URL pubblico con
   HTTPS — in locale non funziona, serve un dominio reale):

   ```bash
   docker compose exec backend python -c "
   from app.integrations.superchat import create_webhook
   print(create_webhook('https://TUO-DOMINIO/webhooks/superchat', ['message_inbound']))
   "
   ```
4. Copia il `secret` restituito in `SUPERCHAT_WEBHOOK_SECRET` nel `.env` e
   riavvia (`docker compose restart backend`).

## 7. Cosa NON è ancora incluso (fasi successive)

- Verifica della firma dei webhook Superchat: lo schema esatto non è
  pubblico nella documentazione, va confermato con il loro supporto prima del
  go-live (vedi commento in `backend/app/integrations/superchat.py`).
- Analisi foto, risposte vocali del tutor, dashboard statistiche avanzate,
  multilingua — previsti come "funzioni successive" nel documento di
  architettura, non nell'MVP.
- Informativa privacy/GDPR: da preparare (vedi documento di architettura).
- Test con un vero account Superchat e con Postgres in esecuzione reale.

## 8. Struttura tecnica, in breve

- **Database**: PostgreSQL + pgvector (`backend/db/schema.sql`).
- **Backend**: FastAPI (Python). Il flusso di risposta è in
  `backend/app/rag/generate.py`: recupero → soglia di affidabilità → verifica
  conflitti → generazione con Claude → controllo di fondatezza (le
  affermazioni della risposta vengono ricontrollate contro le fonti prima di
  mostrarle) → citazioni.
- **Frontend**: Next.js (React). Chat mobile-first in `frontend/app/chat`,
  pannello admin in `frontend/app/admin`.
- **Prompt di sistema** del tutor: `backend/app/rag/prompt.py`.
