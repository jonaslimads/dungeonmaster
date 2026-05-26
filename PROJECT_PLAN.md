# Project Plan — dungeonmaster

Voice-first RPG assistant with RAG-powered rulebook knowledge.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        HAProxy                               │
│              :80 → web, voice, rag (SSL)                     │
└────┬──────────────┬──────────────────┬──────────────────────┘
     │              │                  │
     ▼              ▼                  ▼
  ┌──────┐     ┌────────┐        ┌────────┐
  │ web  │     │ voice  │        │  rag   │
  │:3000 │     │ :8000  │        │ :8000  │
  └──────┘     └───┬────┘        └───┬────┘
                   │                  │
                   │                  │
              ┌────▼──────────────────▼────┐
              │      Local LLM Server       │
              │  Ollama / vLLM / LMStudio   │
              │                             │
              │  whisper-base   (STT)       │
              │  kokoro          (TTS)      │
              │  qwen3.6-27b     (chat)     │
              │  gemma-4-31b-pdf (VLM/OCR)  │
              └─────────────────────────────┘
```

---

## Services

### `web` — Next.js Frontend

**Status:** ✅ Running

**Purpose:** Push-to-talk UI for voice conversations with the RPG assistant.

**Tech:** Next.js, React, TypeScript, Tailwind CSS

**Key files:**
```
web/
├── src/
│   ├── app/
│   │   ├── layout.tsx        # Root layout, metadata
│   │   ├── page.tsx          # Home page, warmup trigger
│   │   └── globals.css       # Global styles
│   ├── components/
│   │   └── PushToTalk.tsx    # Main UI: record, messages, TTS
│   └── lib/
│       └── api.ts            # API client (sendAudio, sendText, playAudio)
├── package.json
└── Dockerfile
```

**Flow:**
1. User opens home page → `POST /api/warmup` loads models
2. User holds button → records audio via MediaRecorder
3. Audio sent to `voice` service → STT → LLM → TTS → plays response
4. Text messages also supported via `POST /api/turn/text`

**Future:**
- [ ] Campaign dashboard
- [ ] RAG search interface
- [ ] Visual asset gallery (maps, monster art)

---

### `voice` — Voice Proxy Service

**Status:** ✅ Running

**Purpose:** Orchestrates the voice conversation pipeline: STT → LLM → TTS.

**Tech:** FastAPI, Python 3.12+, uv

**Models used:**
| Model | Purpose | Provider |
|-------|---------|----------|
| `qwen3.6-27b-mtp-140k` | Chat / RPG replies | Ollama |
| `whisper-base` | Speech-to-text | Ollama |
| `kokoro` | Text-to-speech | Kokoro-FastAPI |

**Key files:**
```
voice/
├── src/voice/
│   ├── main.py                    # FastAPI app, lifespan, DI, warmup endpoint
│   ├── config.py                  # Settings (LLM, STT, TTS URLs, auth)
│   ├── models/
│   │   ├── turn.py                # Turn domain model
│   │   └── conversation.py        # Conversation domain model
│   ├── services/
│   │   ├── llm_service.py         # Chat generation (system prompt + user message)
│   │   ├── stt_service.py         # Audio transcription wrapper
│   │   ├── tts_service.py         # Speech synthesis wrapper
│   │   └── audio_service.py       # Directory management
│   ├── clients/
│   │   ├── llm_client.py          # HTTP client for LLM (chat completions)
│   │   ├── stt_client.py          # HTTP client for STT (whisper)
│   │   └── tts_client.py          # HTTP client for TTS (kokoro)
│   ├── auth/
│   │   └── token.py               # Bearer token verification
│   └── routers/
│       ├── turns_requests.py      # TextTurnRequest
│       ├── turns_responses.py     # TurnResponse
│       └── turns_router.py        # POST /api/turn/audio, POST /api/turn/text
```

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/warmup` | Load all models into memory (called by web on home load) |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/turn/audio` | Full voice turn: audio → STT → LLM → TTS → SSE stream |
| `POST` | `/api/turn/text` | Text turn: message → LLM → SSE stream |

**Audio pipeline (`/api/turn/audio`):**
```
Upload audio (webm)
  ↓
ffmpeg → WAV (16kHz, mono)
  ↓
whisper STT → transcript
  ↓
LLM chat → assistant reply
  ↓
kokoro TTS → MP3 audio
  ↓
SSE stream back to client
```

**SSE events:**
```
received → transcript → assistant → audio → done
```

**Future:**
- [ ] Conversation memory / context window management
- [ ] Multiple character voices per session
- [ ] RAG-augmented LLM responses

---

### `rag` — PDF Extraction and Ingestion Service

**Status:** ✅ Running (extraction pipeline complete)

**Purpose:** Ingest RPG rulebook PDFs, extract text and visual assets, produce canonical documents for future RAG retrieval.

**Tech:** FastAPI, Python 3.12+, PyMuPDF, Pillow, uv

**Models used:**
| Model | Purpose | Optional? |
|-------|---------|-----------|
| `gemma-4-31b-pdf` | VLM: layout analysis, OCR, visual asset detection | Yes |

**Key files:**
```
rag/
├── src/rag/
│   ├── main.py                    # FastAPI app, lifespan, DI
│   ├── config.py                  # Settings (VLM URL, data dirs, batch size)
│   ├── models/
│   │   ├── source.py              # Source (PDF metadata, status)
│   │   ├── page.py                # ExtractedPage (canonical page)
│   │   ├── block.py               # PageBlock (text block on page)
│   │   ├── extraction_job.py      # ExtractionJob (pipeline job tracking)
│   │   ├── image_asset.py         # ImageAsset + BoundingBox
│   │   ├── canonical_document.py  # Section (document sections)
│   │   └── chunk.py               # Chunk (parent/child chunks, future)
│   ├── services/
│   │   ├── source_service.py      # Register PDF, create dirs, list sources
│   │   ├── page_rendering_service.py  # PDF → PNG images (batches)
│   │   ├── native_text_service.py # PyMuPDF text extraction (batches)
│   │   ├── ocr_service.py         # VLM OCR fallback (Gemma 4)
│   │   ├── layout_service.py      # VLM layout analysis (Gemma 4)
│   │   ├── visual_asset_service.py # Validate bounding boxes, create assets
│   │   ├── image_cropping_service.py # Crop images from page PNGs
│   │   ├── markdown_service.py    # Build pages.jsonl + book.md
│   │   ├── ingestion_service.py   # Orchestrate full pipeline (batched)
│   │   ├── extraction_service.py  # Job management (create, run, status)
│   │   └── chunking_service.py    # Placeholder for Phase 2
│   ├── clients/
│   │   ├── pdf_client.py          # PyMuPDF wrapper (render, extract)
│   │   ├── ocr_client.py          # VLM OCR client (Gemma 4)
│   │   ├── vlm_client.py          # VLM layout + asset detection (Gemma 4)
│   │   └── storage_client.py      # Filesystem operations (JSONL, dirs)
│   └── routers/
│       ├── health_router.py       # GET /health
│       ├── sources_requests.py    # RegisterLocalSourceRequest
│       ├── sources_responses.py   # SourceResponse, SourcesListResponse
│       ├── sources_router.py      # POST /sources/register-local, GET /sources
│       ├── extraction_requests.py # CreateExtractionJobRequest
│       ├── extraction_responses.py # ExtractionJobResponse
│       └── extraction_router.py   # POST /extraction/jobs, GET/POST /jobs/{id}
```

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/sources/register-local` | Register PDF from `data/pdfs/` |
| `GET` | `/sources` | List all registered sources |
| `GET` | `/sources/{source_id}` | Get source details |
| `POST` | `/extraction/jobs` | Create extraction job |
| `GET` | `/extraction/jobs/{job_id}` | Get job status |
| `POST` | `/extraction/jobs/{job_id}/run` | Run extraction job |

**Extraction pipeline:**
```
[1] Register source
    Copy PDF from data/pdfs/ → data/rag/sources/<id>/original/source.pdf

[2] Render pages (batch of 10)
    PyMuPDF → pages/page_0001.png, page_0002.png, ...

[3] Extract native text (batch of 10)
    PyMuPDF → extracted/native_text.jsonl

[4] VLM analysis (optional, use_vlm=true)
    Gemma 4 → extracted/vlm_layout.jsonl
    → extracted/image_assets.jsonl
    → assets/images/page_NNNN_img_NNN.png
    → assets/thumbnails/page_NNNN_img_NNN.webp

[5] Build canonical (batch of 10, append)
    → canonical/pages.jsonl
    → canonical/book.md (rebuilt at end)

[6] Quality report
    → reports/quality_report.md
```

**Pipeline resume:** Processes in batches of 10 pages. By default resumes from the last processed page. Use `force=true` to restart.

**Script:** `./ingest-sources.sh` — registers and processes all 3 D&D 5E PDFs.

**Current sources:**
| Source ID | PDF | Type |
|-----------|-----|------|
| `dnd_5e_players_handbook` | D.D.5E.-.Livro.do.Jogador.Fundo.Colorido.pdf | core_rulebook |
| `dnd_5e_dungeon_masters_guide` | D.D.5E.-.Guia.do.Mestre.pdf | core_rulebook |
| `dnd_5e_monster_manual` | D.D.5E.-.Manual.dos.Monstros.pdf | monster_book |

**Future:**
- [ ] Phase 2: Chunking (parent + child chunks from book.md)
- [ ] Phase 3: Embeddings + vector index (pgvector)
- [ ] Phase 4: Retrieval endpoints for voice service
- [ ] OCR fallback for low-confidence pages
- [ ] Asset gallery API

---

## Data Flow

### Voice conversation
```
User speaks → web (PushToTalk)
  → POST /api/turn/audio (voice)
    → ffmpeg convert → whisper STT → LLM chat → kokoro TTS
    → SSE stream back to web
  → User hears response
```

### RAG ingestion
```
PDF in data/pdfs/
  → POST /sources/register-local (rag)
  → POST /extraction/jobs (rag)
  → POST /extraction/jobs/{id}/run (rag)
  → data/rag/sources/<id>/canonical/book.md
  → data/rag/sources/<id>/canonical/pages.jsonl
  → data/rag/sources/<id>/assets/images/ (optional)
```

### Future: RAG-augmented voice
```
User asks about D&D rules
  → voice service queries rag service
  → rag returns relevant chunks + assets
  → LLM generates response with context
  → TTS speaks response
```

---

## Infrastructure

### Docker Compose services
| Service | Port | Description |
|---------|------|-------------|
| `proxy` | 80, 443 | HAProxy reverse proxy + SSL |
| `web` | 3000 (internal) | Next.js frontend |
| `voice` | 8000 (internal) | Voice proxy |
| `rag` | 8002 → 8000 | RAG extraction (host:container) |

### Shared volumes
- `./data:/app/data` — shared between voice and rag
- `./voice/src:/app/src` — hot reload for voice
- `./rag/src:/app/src` — hot reload for rag
- `./web:/app` — hot reload for web

### Local LLM server (external)
Runs separately on `192.168.0.141:19000`. All services connect to it via HTTP. Models are loaded on demand by `POST /api/warmup`.

---

## Development Commands

```bash
# All services
docker compose up -d

# Rebuild a specific service
docker compose up -d --build <service>

# Run rag ingestion script
./ingest-sources.sh

# Run rag with VLM (slower, but extracts images)
USE_VLM=true ./ingest-sources.sh

# Force re-extraction from scratch
FORCE=true ./ingest-sources.sh

# Run tests
cd voice && uv run pytest tests/ -v
cd rag && uv run pytest tests/ -v

# Run a service locally
cd voice && uv run uvicorn voice.main:app --reload
cd rag && uv run uvicorn rag.main:app --reload
```

---

## Phase Roadmap

### Phase 1: Extraction ✅ (current)
- [x] Register PDFs from `data/pdfs/`
- [x] Render pages to PNG
- [x] Extract native text with PyMuPDF
- [x] Build canonical `pages.jsonl` + `book.md`
- [x] Quality report generation
- [x] Batch processing with resume
- [x] VLM layout analysis (optional)
- [x] Visual asset detection and cropping
- [x] Image asset metadata

### Phase 2: Chunking
- [ ] Split `book.md` into sections
- [ ] Generate parent chunks (sections)
- [ ] Generate child chunks (paragraphs, stat blocks)
- [ ] Link chunks to visual assets
- [ ] Save `sections.jsonl`, `parent_chunks.jsonl`, `child_chunks.jsonl`

### Phase 3: Indexing
- [ ] Generate embeddings for chunks
- [ ] Store in pgvector
- [ ] Build retrieval API

### Phase 4: RAG Integration
- [ ] Voice service queries rag for context
- [ ] LLM generates responses with rulebook context
- [ ] Return relevant visual assets with responses
- [ ] Frontend displays assets alongside text

### Phase 5: Campaign Features
- [ ] Campaign management
- [ ] Session transcripts with RAG citations
- [ ] Character sheet integration
- [ ] Visual asset gallery in frontend
