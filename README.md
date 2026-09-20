# selfie.Me

A starter project for a privacy-first personal memory AI product.

This repository contains a basic MVP scaffold aligned with the strategic documents:
- capture personal memories and reflections
- preserve provenance and user control
- structure evidence, beliefs, and decisions
- provide grounded retrieval and reflection experiences

## Structure

- `backend/`: FastAPI API service
- `frontend/`: Next.js app shell
- `docker-compose.yml`: local services for Postgres and Redis

## Quick start

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Product intent

The current version is intentionally simple and focused on the founder pilot:
- daily voice/text capture
- searchable memory archive
- belief and decision timeline
- evidence-backed reflection queries
- safe privacy controls

## Notes

This is a scaffold only. It is designed to be extended with real storage, auth, AI pipelines, and user feedback loops.
