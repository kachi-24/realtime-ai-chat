# Real-Time AI Chat + RAG

A full-stack real-time AI chat application built with **FastAPI, React, WebSockets, PostgreSQL, pgvector, Redis, RQ, JWT authentication, and Ollama**.

The project combines real-time communication, retrieval-augmented generation (RAG), background document processing, vector search, authentication, rate limiting, caching, and observability into a distributed-style AI application.

---

## 🚀 Features

### 💬 Real-Time AI Chat

* Real-time communication using **WebSockets**
* Streaming AI responses from Ollama
* Persistent conversations and messages
* Automatic conversation titles based on the first user message
* Feature flag for enabling/disabling automatic conversation titles
* Conversation history
* Multi-user conversation isolation

### 🧠 Retrieval-Augmented Generation (RAG)

* Upload documents for knowledge retrieval
* PDF/text document processing
* Document chunking
* Vector embeddings
* PostgreSQL + **pgvector** for vector storage
* Similarity-based document retrieval
* User-specific document isolation
* Retrieved context is provided to the AI before generating an answer

### 🤖 Local AI

The application uses **Ollama** for local LLM inference.

Current model configuration:

```text
qwen3:1.7b
```

The application is designed to avoid requiring a third-party AI API key for inference.

---

## 🔐 Authentication & Security

The backend includes:

* User registration
* Password hashing
* JWT authentication
* Access tokens
* Refresh tokens
* Email verification
* Protected API endpoints
* Protected WebSocket connections
* User-specific conversations
* User-specific documents
* User-specific RAG retrieval
* Rate limiting
* CORS configuration
* Secure HTTP-only authentication cookies where applicable

The application ensures that users cannot retrieve conversations or document chunks belonging to another user.

---

## ⚡ Redis

Redis is used for distributed application functionality including:

* Rate limiting
* Caching
* Background job infrastructure
* Queue communication

This allows the application to separate short-lived application state and background processing from the main PostgreSQL database.

---

## 🔄 Background Processing

Document processing is handled asynchronously using:

* **Redis**
* **RQ (Redis Queue)**
* Dedicated worker processes

Instead of making the API server perform expensive document-processing tasks directly, uploaded documents can be placed into a background queue.

Example flow:

```text
User uploads document
        │
        ▼
FastAPI API
        │
        ▼
Redis Queue
        │
        ▼
RQ Worker
        │
        ├── Load document
        ├── Extract text
        ├── Split into chunks
        ├── Generate embeddings
        └── Store vectors in PostgreSQL
```

This improves responsiveness and provides a foundation for scaling document processing independently from the API.

---

## 🗄️ Database

The project uses **PostgreSQL** as the primary database.

PostgreSQL stores:

* Users
* Conversations
* Messages
* Documents
* Document chunks
* Vector embeddings
* Authentication-related data

### Vector Search

The project uses the PostgreSQL **pgvector** extension to store and search embeddings.

RAG flow:

```text
Document
   │
   ▼
Text Extraction
   │
   ▼
Chunking
   │
   ▼
Embeddings
   │
   ▼
PostgreSQL + pgvector
   │
   ▼
Similarity Search
   │
   ▼
Relevant Context
   │
   ▼
Ollama
   │
   ▼
AI Response
```

---

## 🏗️ Architecture

```text
                         ┌──────────────────────┐
                         │      React UI        │
                         │      Frontend        │
                         └──────────┬───────────┘
                                    │
                         HTTP / WebSocket
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      FastAPI         │
                         │       Backend        │
                         └───────┬───────┬──────┘
                                 │       │
                    ┌────────────┘       └─────────────┐
                    │                                  │
                    ▼                                  ▼
             ┌──────────────┐                  ┌──────────────┐
             │ PostgreSQL   │                  │    Redis     │
             │ + pgvector   │                  │              │
             └──────────────┘                  └──────┬───────┘
                                                      │
                                                      ▼
                                               ┌──────────────┐
                                               │  RQ Worker   │
                                               │              │
                                               └──────┬───────┘
                                                      │
                                                      ▼
                                               Document Jobs
                                                      │
                                                      ▼
                                               Embeddings/RAG

                         ┌──────────────────────┐
                         │       Ollama         │
                         │     Local LLM        │
                         └──────────────────────┘
```

---

## 🛠️ Technology Stack

### Frontend

* React
* Vite
* JavaScript
* WebSocket API
* Web Speech API

### Backend

* Python
* FastAPI
* WebSockets
* SQLAlchemy
* Alembic
* JWT
* Pydantic

### AI / RAG

* Ollama
* Qwen
* Vector embeddings
* pgvector
* Retrieval-Augmented Generation

### Infrastructure

* PostgreSQL
* Redis
* RQ
* Docker
* Docker Compose

### Testing & CI/CD

* Pytest
* Python compile checks
* npm build
* GitHub Actions

### Observability

* Sentry

---

## 📁 Project Structure

```text
realtime-ai-chat/
│
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── auth.py
│   ├── dependencies.py
│   ├── redis_client.py
│   ├── redis_queue.py
│   ├── rate_limiter.py
│   ├── cache.py
│   ├── email_service.py
│   ├── worker.py
│   │
│   ├── conversation_title.py
│   ├── feature_flags.py
│   │
│   ├── jobs/
│   │   └── document_jobs.py
│   │
│   ├── rag/
│   │   ├── loader.py
│   │   ├── chunker.py
│   │   ├── embeddings.py
│   │   ├── retriever.py
│   │   └── prompt.py
│   │
│   ├── alembic/
│   │   └── versions/
│   │
│   └── uploads/
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── ...
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── docker-compose.yaml
├── .gitignore
└── README.md
```

---

## 🔄 Conversation Flow

A normal AI chat request follows this general flow:

```text
User
 │
 ▼
React Frontend
 │
 │ WebSocket
 ▼
FastAPI
 │
 ├── Authenticate user
 │
 ├── Apply rate limit
 │
 ├── Load conversation
 │
 ├── Save user message
 │
 ├── Retrieve relevant RAG context
 │
 ▼
Ollama
 │
 ▼
Stream AI response
 │
 ▼
FastAPI
 │
 ▼
React
 │
 ▼
User
```

---

## 📄 Document Processing Flow

```text
User
 │
 ▼
Upload PDF/Text File
 │
 ▼
FastAPI
 │
 ▼
Redis / RQ Queue
 │
 ▼
Background Worker
 │
 ▼
Extract Text
 │
 ▼
Chunk Document
 │
 ▼
Generate Embeddings
 │
 ▼
PostgreSQL + pgvector
```

When the user asks a question:

```text
Question
   │
   ▼
Generate Query Embedding
   │
   ▼
pgvector Similarity Search
   │
   ▼
Relevant Document Chunks
   │
   ▼
Build RAG Prompt
   │
   ▼
Ollama
   │
   ▼
Generated Answer
```

---

## 🏷️ Automatic Conversation Titles

New conversations can automatically receive a title based on the user's first message.

Example:

```text
User:
"Explain how JWT refresh tokens work"

Conversation title:
"How JWT Refresh Tokens Work"
```

This functionality is controlled through a feature flag, allowing the feature to be enabled or disabled without removing the implementation.

---

## 🎤 Voice Input

The frontend supports voice-to-text using the browser's **Web Speech API**.

Users can speak their message instead of typing it.

```text
Microphone
    │
    ▼
Web Speech API
    │
    ▼
Transcribed Text
    │
    ▼
Chat Message
```

Browser support may vary depending on the browser and platform.

---

## 📊 Observability

The application integrates **Sentry** for error monitoring and performance visibility.

Sentry is configured across the appropriate backend, worker, and frontend components to help detect unexpected errors and monitor application behavior.

Sensitive authentication information and secrets should not be sent to Sentry.

---

## 🧪 Testing

Backend tests use **pytest**.

Run the backend tests:

```bash
cd backend
pytest -q
```

Compile the backend:

```bash
python -m compileall .
```

Build the frontend:

```bash
cd frontend
npm run build
```

---

## 🔁 CI/CD

GitHub Actions automatically validates the project.

The CI pipeline performs:

### Backend

```text
Checkout
   ↓
Python setup
   ↓
Install dependencies
   ↓
Compile backend
   ↓
Run pytest
```

### Frontend

```text
Checkout
   ↓
Node.js setup
   ↓
npm ci
   ↓
npm run build
```

This helps catch backend and frontend errors before deployment.

---

## 🐳 Docker

Docker is used to containerize the backend and background worker.

The project uses Docker Compose for the application services.

Example:

```bash
docker compose up --build
```

Stop the project when finished:

```bash
docker compose down
```

> Do not use `docker compose down -v` unless you intentionally want to remove Docker volumes and their stored data.

---

## ⚙️ Local Development

### 1. Clone the repository

```bash
git clone https://github.com/kachi-24/realtime-ai-chat.git
```

```bash
cd realtime-ai-chat
```

### 2. Create a Python virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configure environment variables

Create your local environment configuration with the required values for:

* PostgreSQL
* Redis
* JWT authentication
* Email verification
* Ollama
* Sentry
* Frontend configuration

**Never commit real secrets or API keys to GitHub.**

### 5. Start Ollama

Make sure Ollama is installed and the configured model is available.

Example:

```bash
ollama pull qwen3:1.7b
```

Check available models:

```bash
ollama list
```

### 6. Start the backend

From the `backend` directory:

```bash
uvicorn main:app --reload --port 8000
```

### 7. Start the frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

---

## 🔑 Environment Variables

The application uses environment variables for configuration and secrets.

Typical configuration includes:

```env
DATABASE_URL=
REDIS_URL=

JWT_SECRET_KEY=
ACCESS_TOKEN_EXPIRE_MINUTES=
REFRESH_TOKEN_EXPIRE_DAYS=

EMAIL_VERIFICATION_EXPIRE_HOURS=
RESEND_API_KEY=
EMAIL_FROM=

OLLAMA_URL=
OLLAMA_MODEL=

SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=
```

For the frontend, Vite variables use the `VITE_` prefix:

```env
VITE_API_URL=
VITE_WS_URL=
VITE_ENVIRONMENT=
VITE_SENTRY_DSN=
VITE_SENTRY_TRACES_SAMPLE_RATE=
```

Do not commit `.env` files or real credentials.

---

## 🔒 Security

This project is designed with several security considerations:

* Password hashing
* JWT authentication
* Refresh-token authentication
* Email verification
* Protected WebSocket connections
* User-level resource isolation
* Rate limiting
* CORS restrictions
* Environment-based secrets
* Sentry error monitoring without intentionally exposing authentication secrets

For production deployment, additional infrastructure security such as HTTPS, secure cookies, secret management, database security, network restrictions, and production-grade monitoring should be configured.

---

## 📈 Distributed Systems Concepts

This project is also designed to demonstrate practical distributed-systems concepts.

### Stateless API

Authentication allows API instances to remain largely stateless, making horizontal scaling possible.

### Redis

Redis provides shared state and infrastructure for:

* Rate limiting
* Caching
* Background queues

### Background Workers

Document processing is separated from the API server using RQ workers.

This allows worker capacity to be scaled independently.

### WebSockets

The application maintains real-time communication between clients and the backend.

For a multi-instance production deployment, WebSocket coordination would require shared infrastructure such as Redis Pub/Sub or another message-broker architecture.

### Database

PostgreSQL provides durable persistent storage while pgvector enables vector similarity search.

---

## 🚧 Current Development Status

The project currently includes:

* [x] React frontend
* [x] FastAPI backend
* [x] WebSocket chat
* [x] Ollama local inference
* [x] PostgreSQL
* [x] Redis
* [x] RQ background jobs
* [x] Document upload
* [x] RAG pipeline
* [x] pgvector similarity search
* [x] JWT authentication
* [x] Refresh tokens
* [x] Email verification
* [x] User-level data isolation
* [x] Rate limiting
* [x] Voice-to-text
* [x] Automatic conversation titles
* [x] Feature flags
* [x] Sentry integration
* [x] Automated CI
* [x] Docker support

---

## 🛣️ Future Improvements

Possible future improvements include:

* Horizontal backend scaling
* Redis Pub/Sub for multi-instance WebSocket communication
* Production GPU inference infrastructure
* Model load balancing
* Object storage for uploaded documents
* Database connection pooling and read replicas
* Advanced RAG evaluation
* Hybrid keyword + vector search
* Streaming RAG responses
* Improved conversation-title generation using an LLM
* Production deployment
* Infrastructure monitoring
* Automated deployment through CI/CD

---

## 🎯 Project Goals

The goal of this project is to build more than a simple AI chatbot.

It demonstrates how modern AI applications can combine:

```text
AI
+
RAG
+
WebSockets
+
Authentication
+
Databases
+
Vector Search
+
Redis
+
Background Workers
+
Docker
+
CI/CD
+
Observability
```

into a single full-stack application.

---

## 👨‍💻 Author

**Agbo Onyedikachi**

Software Engineering Student & Developer

GitHub: [@kachi-24](https://github.com/kachi-24)

---

## 📜 License

This project is currently intended for educational and portfolio purposes.
