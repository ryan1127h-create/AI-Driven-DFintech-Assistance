# AI-Driven-DFintech-Assistance
This is a repository for AI-Driven Assistance in DFintech

# Project Setup Guide

This project consists of three main components:

- **backend** – Handles data retrieval and storage with Supabase.
- **agent-backend** – Hosts the AI agents and FastAPI services.
- **frontend** – React frontend application.

---

## Backend

Used to retrieve and manage data from Supabase.

### Setup & Run

```bash
cd backend
npm install
node server.js
```

---

## Agent Backend

Used to manage AI agents, workflows, and API services.

### Setup

```bash
cd agent-backend

pip install -r requirements.txt
pip install werkzeug flask langchain-openai
```

### Run

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at:

```text
http://localhost:8000
```

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

---

## Startup Order

For local development, start the services in the following order:

1. Backend
2. Agent Backend
3. Frontend

```bash
# Terminal 1
cd backend
node server.js

# Terminal 2
cd agent-backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 3
cd frontend
npm run dev
```

---

## Project Structure

```text
project-root/
│
├── backend/          # Supabase data service
├── agent-backend/    # AI agents and FastAPI services
└── frontend/         # React frontend
```

## Environment Configuration

This project uses multiple configuration files for different services.

---

### DeepSeek Configuration

Place the DeepSeek configuration file in:

```text
agent-backend/data/.deepseek.json
```

Example:

```text
agent-backend/
└── data/
    └── .deepseek.json
```

---

### RAG Backend Environment Variables

Create a `.env` file in:

```text
agent-backend/rag_backend/.env
```

This file should contain:

- Supabase credentials
- Embedding model configuration
- LLM model configuration
- Other RAG-related settings

Example:

```env
SUPABASE_URL=
SUPABASE_KEY=

OPENAI_API_KEY=
OPENAI_MODEL=

EMBEDDING_MODEL=
```

---

### Agent Backend Environment Variables

Create a `.env` file in:

```text
agent-backend/.env
```

This file should contain:

- GROQ API Key
- Redis configuration
- Agent-specific settings

Example:

```env
GROQ_API_KEY=

REDIS_HOST=
REDIS_PORT=
REDIS_PASSWORD=
```

---

## Configuration Structure

```text
project-root/
│
├── backend/
│
├── frontend/
│
└── agent-backend/
    │
    ├── .env                    # GROQ & Redis configuration
    │
    ├── data/
    │   └── .deepseek.json      # DeepSeek configuration
    │
    └── rag_backend/
        └── .env                # Supabase & model configuration
```

---

## Important Notes

- Do **not** commit `.env` files to Git.
- Add all sensitive configuration files to `.gitignore`.
- Ensure all required environment variables are configured before starting the services.
- Restart the application after updating any `.env` file.