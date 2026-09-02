# AI-Driven-DFintech-Assistance
This is a repository for AI-Driven Assistance in DFintech

# Project Setup Guide

This project consists of two main components:

- **backend** – FastAPI service hosting the AI agents, orchestrator, and all business/data endpoints (Postgres via Supabase, Redis, DeepSeek, OpenAI embeddings).
- **frontend** – React frontend application.

---

## Backend

Used to manage AI agents, workflows, and API services.

### Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

Configuration is read from a `.env` file in the repo root (see `render.yaml` for the full list of required variables).

### Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:

```text
http://localhost:8000
```

API docs: `http://localhost:8000/docs`

---

## Frontend

React application for the user interface.

### Setup

```bash
cd frontend
npm install
```

### First-Time Build

```bash
npm run build
```

### Run Development Server

```bash
npm run dev
```

The frontend will be available at:

```text
http://localhost:5173
```

The repo-root `.env`'s `VITE_API_BASE` should point at the backend above (e.g. `http://localhost:8000/api/v1`).

---

## Startup Order

For local development, start the services in the following order:

1. Backend
2. Frontend

```bash
# Terminal 1
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
cd frontend
npm run dev
```

---

## Contributing

Code standards and commit/PR rules: see [CONTRIBUTING.md](CONTRIBUTING.md).

---
