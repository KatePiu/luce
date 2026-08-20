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
  docker-compose.yml   Avvia database + backend + frontend con un solo comando (in locale)
  render.yaml            Configurazione per pubblicare backend+database su Render
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

## 6. Mettere LUCE online (Render + Vercel)

"Caricare i file per renderli accessibili da browser" in pratica significa:
mettere il codice su **GitHub** (un archivio online del progetto, gratuito),
e poi collegare due servizi che lo prendono da lì e lo fanno funzionare 24
ore su 24 — non è come caricare foto su un sito, non si "trascina" nulla a
mano. Con Render (backend + database) e Vercel (chat web) il collegamento è
automatico: ogni volta che il codice su GitHub viene aggiornato, i due
servizi si aggiornano da soli.

Questi due servizi (Render e Vercel) richiedono un account personale: la
creazione dell'account e l'inserimento dei dati di pagamento li devi fare tu
direttamente sul loro sito — io posso preparare tutto il resto ma non posso
creare account o inserire carte di pagamento per conto tuo.

### 6.1 Mettere il codice su GitHub

Il progetto è già pronto in locale come repository git (l'ho preparato io: è
la "cronologia delle versioni" del codice). Ti serve solo un repository
vuoto su GitHub dove spedirlo:

1. Crea un account su <https://github.com> se non ne hai già uno.
2. Crea un nuovo repository vuoto (bottone verde "New"), chiamalo per
   esempio `luce`. **Non** selezionare "Add a README" — deve restare vuoto.
3. GitHub ti mostrerà un indirizzo tipo `https://github.com/tuo-utente/luce.git`.
   Da questa cartella (`LUCE/`), esegui:

   ```bash
   git remote add origin https://github.com/TUO-UTENTE/luce.git
   git branch -M main
   git push -u origin main
   ```

Da questo momento il codice è online su GitHub (privatamente, se hai scelto
repository "Private" in fase di creazione — consigliato, dato che contiene la
logica del tutor).

### 6.2 Backend + database su Render

1. Crea un account su <https://render.com> (puoi accedere direttamente con
   GitHub).
2. "New" → "Blueprint", seleziona il repository `luce` appena creato. Render
   legge automaticamente il file `render.yaml` già incluso nel progetto e
   propone di creare **due risorse**: il database Postgres (con pgvector,
   supportato nativamente da Render) e il backend.
3. Conferma la creazione. La prima build richiede qualche minuto.
4. Aperta la risorsa `luce-backend`, vai su "Environment" e inserisci le
   chiavi segrete che il Blueprint ha lasciato vuote apposta (`ANTHROPIC_API_KEY`,
   `VOYAGE_API_KEY`, `STT_API_KEY`, e quelle di Superchat quando le avrai —
   vedi sezione 7): sono le stesse della tabella nella sezione 2.
5. Crea le tabelle nel database (una volta sola): apri la scheda "Shell" del
   servizio `luce-backend` su Render e lancia:

   ```bash
   python -m scripts.init_db
   ```
6. Crea il primo utente admin, sempre dalla Shell:

   ```bash
   python -m scripts.create_admin nicola.ratti@katepiu.com "una-password-sicura"
   ```
7. Render ti assegna un indirizzo pubblico tipo
   `https://luce-backend.onrender.com` — è l'indirizzo del backend, tienilo
   a portata: serve al passo successivo.

### 6.3 Chat web su Vercel

1. Crea un account su <https://vercel.com> (anche qui, puoi usare GitHub).
2. "Add New" → "Project", seleziona lo stesso repository `luce`.
3. Vercel riconosce automaticamente che è un progetto Next.js. **Un solo
   campo da cambiare**: in "Root Directory" seleziona `frontend` (il
   progetto ha sia il backend sia il frontend nella stessa cartella
   principale, va indicato dove si trova la parte web).
4. In "Environment Variables" aggiungi:
   - `NEXT_PUBLIC_API_BASE` = l'indirizzo del backend Render ottenuto al
     passo precedente (es. `https://luce-backend.onrender.com`)
5. "Deploy". Dopo un paio di minuti ottieni un indirizzo tipo
   `https://luce.vercel.app` — è il link da dare ai parrucchieri per
   accedere da smartphone.
6. Torna su Render, apri `luce-backend` → "Environment", e imposta
   `FRONTEND_ORIGIN` con l'indirizzo Vercel appena ottenuto (es.
   `https://luce.vercel.app`), al posto di `*`: da questo momento solo la
   vostra chat web può parlare con il backend, non chiunque su internet.

Da qui in avanti, ogni volta che il codice viene aggiornato su GitHub (anche
da me, in una conversazione futura), Render e Vercel ripubblicano da soli la
versione nuova — non c'è più nulla da "caricare" a mano.

### 6.4 In alternativa: versione statica via FTP (demo per il cliente)

Se preferisci mostrare la chat al cliente sul tuo hosting FTP esistente
invece di (o in aggiunta a) Vercel, si può fare: la chat web di LUCE non usa
funzioni che richiedono un server Next.js acceso, quindi il progetto è già
configurato per essere esportato come sito statico (solo file HTML/CSS/JS),
caricabile via FTP su un hosting condiviso qualsiasi.

**Limite importante da capire prima**: questo vale solo per la parte
*grafica* della chat. Il "cervello" del tutor (backend + database) non può
girare su un hosting FTP condiviso — quello resta su Render, come nella
sezione 6.2, sempre acceso e raggiungibile da internet. La versione FTP è
solo la vetrina che il cliente vede nel browser; per funzionare deve
comunque parlare con il backend su Render.

Procedura:

1. Assicurati che il backend sia già online su Render (sezione 6.2) — ti
   serve il suo indirizzo, es. `https://luce-backend.onrender.com`.
2. Nella cartella `frontend/`, crea un file chiamato `.env.production.local`
   con questa riga (con il vero indirizzo del backend):
   ```
   NEXT_PUBLIC_API_BASE=https://luce-backend.onrender.com
   ```
3. Genera la versione statica:
   ```bash
   cd frontend
   npm install
   npm run build
   ```
   Viene creata una cartella `frontend/out/` con tutti i file pronti — è
   quella da caricare, non l'intera cartella `frontend`.
4. Con un client FTP (es. FileZilla, o quello del tuo pannello hosting),
   collegati con le credenziali del tuo hosting e carica **tutto il
   contenuto** di `frontend/out/` (non la cartella stessa, il suo contenuto)
   nella cartella pubblica del sito (spesso chiamata `public_html`, `www` o
   `htdocs`).
5. **Importante**: la pagina va messa alla radice di un dominio o
   sottodominio (es. `https://demo-luce.tuosito.it/`), non dentro una
   sottocartella (es. `.../demo/luce/`) — i file generati si aspettano di
   essere serviti dalla radice. Se hai un sottodominio libero, è la scelta
   più semplice; se serve davvero una sottocartella, dimmelo e adeguo la
   configurazione (`basePath` in `frontend/next.config.js`).
6. Su Render, apri `luce-backend` → "Environment" → `FRONTEND_ORIGIN` e
   aggiungi l'indirizzo della demo separato da virgola, es.:
   ```
   https://luce.vercel.app,https://demo-luce.tuosito.it
   ```
   Senza questo passaggio il backend rifiuta le richieste della demo per
   sicurezza (CORS).

Ogni volta che aggiorni il codice, va ripetuto solo il passo 3 (rigenerare
`out/`) e il passo 4 (ricaricare via FTP) — a differenza di Render/Vercel,
qui non c'è pubblicazione automatica.

## 7. Collegare Superchat (WhatsApp)

1. Attiva l'account Superchat (vedi documento di architettura per il costo da
   verificare separatamente dal budget di €100/mese).
2. Prendi `SUPERCHAT_API_KEY` e `SUPERCHAT_CHANNEL_ID` dalla loro dashboard,
   mettili tra le variabili d'ambiente di `luce-backend` su Render (o nel
   `.env` locale se stai ancora testando in locale).
3. Esegui una volta sola, dalla Shell del servizio su Render (serve un URL
   pubblico HTTPS reale — quello di Render, non funziona in locale):

   ```bash
   python -c "
   from app.integrations.superchat import create_webhook
   print(create_webhook('https://luce-backend.onrender.com/webhooks/superchat', ['message_inbound']))
   "
   ```
4. Copia il `secret` restituito nella variabile `SUPERCHAT_WEBHOOK_SECRET` su
   Render e riavvia il servizio ("Manual Deploy" → "Deploy latest commit", o
   basta salvare la variabile: Render riavvia da solo).

## 8. Cosa NON è ancora incluso (fasi successive)

- Verifica della firma dei webhook Superchat: lo schema esatto non è
  pubblico nella documentazione, va confermato con il loro supporto prima del
  go-live (vedi commento in `backend/app/integrations/superchat.py`).
- Analisi foto, risposte vocali del tutor, dashboard statistiche avanzate,
  multilingua — previsti come "funzioni successive" nel documento di
  architettura, non nell'MVP.
- Informativa privacy/GDPR: da preparare (vedi documento di architettura).
- Test con un vero account Superchat e con Postgres in esecuzione reale.

## 9. Struttura tecnica, in breve

- **Database**: PostgreSQL + pgvector (`backend/db/schema.sql`).
- **Backend**: FastAPI (Python). Il flusso di risposta è in
  `backend/app/rag/generate.py`: recupero → soglia di affidabilità → verifica
  conflitti → generazione con Claude → controllo di fondatezza (le
  affermazioni della risposta vengono ricontrollate contro le fonti prima di
  mostrarle) → citazioni.
- **Frontend**: Next.js (React). Chat mobile-first in `frontend/app/chat`,
  pannello admin in `frontend/app/admin`.
- **Prompt di sistema** del tutor: `backend/app/rag/prompt.py`.
