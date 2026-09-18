# CIMET AI Hiring Hackathon 2026

Scaffold prepped ahead of the problem statement (19 Sep 2026, Jaipur). Goal: zero setup friction on the day — clone in, drop in the problem statement, start building.

## Stack

- **Backend:** FastAPI (Python 3.11) — `backend/`
- **Frontend:** React + TypeScript + Vite + Tailwind v4 — `frontend/`
- **LLM:** Anthropic Claude, via `backend/app/services/llm.py`
- **Data/exploration:** `notebooks/` (Jupyter), `data/` (gitignored, drop datasets here)

Covers the JD's three focus areas out of the box:
- **Conversational AI / LLM** → `app/services/llm.py` + `app/routers/chat.py`
- **Knowledge retrieval / RAG** → `app/services/rag.py` (in-memory embeddings + Claude)
- **Recommendation systems** → `app/services/recommender.py` (TF-IDF content-based skeleton, swap for collaborative/hybrid as needed)

## Domain context

CIMET (Sydney-based) builds **digital platforms and customer engagement solutions for brands**. Themes for Final Hack Day (19 Sep) aren't published yet ("revealing soon" as of prep time), but given the JD and company focus, the problem is likely to land on: **personalization/recommendations, conversational AI/chatbots, or customer engagement analytics**. The three skeletons below are chosen to cover those bases.

## Quickstart

### Backend

```bash
cd backend
.venv/Scripts/activate   # Windows
cp .env.example .env     # then fill in ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm run dev
```

Runs on `http://localhost:5173`, proxies `/api/*` to the backend (see `vite.config.ts`).

## When the problem statement drops

1. Skim it, identify which of the three skeletons (chat / RAG / recommender) is closest to the ask.
2. Drop any provided dataset into `data/`.
3. Explore it in a notebook (`jupyter lab` from `backend/` with the venv active) before touching the API.
4. Extend the relevant `app/services/*.py` + router; wire the frontend panel in `App.tsx` to match.
5. Keep committing — `git init` is already done locally.

## Still to do before the day

- [ ] Fill in `backend/.env` with a real `ANTHROPIC_API_KEY`
- [ ] Decide if you want a GitHub remote (currently local-only git repo)
- [ ] Skim CIMET's site / any public info for domain context (industry, product)
