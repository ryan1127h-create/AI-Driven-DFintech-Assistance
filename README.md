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