# Real-Time AI Chat + RAG

A full-stack, real-time AI chat application built with **React, FastAPI, WebSockets, PostgreSQL, pgvector, Redis, RQ, JWT authentication, and Ollama**.

The application combines conversational AI, Retrieval-Augmented Generation (RAG), web search, image understanding, background document processing, vector search, authentication, and error monitoring in a distributed-style architecture.

---

## 🚀 Features

### 💬 Real-Time AI Chat
- Real-time messaging using WebSockets.
- Streaming AI responses.
- Persistent conversations and messages.
- Conversation history.
- Automatic conversation titles.
- Feature flags for controlling application functionality.
- Multi-user conversation isolation.

### 🧠 Retrieval-Augmented Generation (RAG)
- Upload PDF and text documents.
- Extract and process document content.
- Split documents into smaller chunks.
- Generate vector embeddings.
- Store embeddings using PostgreSQL and pgvector.
- Perform similarity-based document retrieval.
- Retrieve user-specific document context.
- Generate responses using relevant retrieved information.

### 🌐 Web Search
- Optional web search during AI conversations.
- Tavily-powered search integration.
- Retrieve external information to supplement AI responses.
- Provide source links alongside web-grounded responses.
- Use web evidence to improve answers about current information.

### 🖼️ Image Understanding
- Image upload and processing.
- Cloudinary integration for image hosting.
- Gemini Vision integration for image understanding.
- Image validation before processing.

### 🤖 Local AI Inference
The application supports local AI inference through **Ollama**.

Current model configuration:

```text
qwen3:1.7b
```

The local inference approach reduces dependence on paid third-party inference APIs.

### 🎤 Voice Input
- Voice-to-text using the browser Web Speech API.
- Convert spoken input into chat messages.

### 🔐 Authentication & Security
- User registration.
- Password hashing.
- JWT authentication.
- Access and refresh tokens.
- Email verification.
- Protected API endpoints.
- Protected WebSocket connections.
- User-specific conversations and documents.
- Rate limiting.
- CORS configuration.
- Secure HTTP-only authentication cookies where applicable.

### ⚡ Redis & Background Processing
Redis supports:
- Rate limiting.
- Caching.
- Background job infrastructure.
- Queue communication.

RQ workers handle document-processing jobs independently of the main API server.

### 📊 Observability
- Sentry integration for frontend and backend error monitoring.
- Worker error monitoring.
- Error reporting for background jobs.

---

## 🏗️ Architecture

```text
                    React Frontend
                          |
                    HTTP / WebSocket
                          |
                          v
                    FastAPI Backend
                          |
          +---------------+----------------+
          |               |                |
          v               v                v
      PostgreSQL        Redis          AI Services
      + pgvector          |          + Ollama
                          |          + Tavily
                          v          + Gemini Vision
                      RQ Worker
                          |
                          v
                  Document Processing
                          |
                          v
                 Embeddings and RAG
```

### RAG Processing Flow

```text
User uploads document
        |
        v
    FastAPI
        |
        v
    Redis Queue
        |
        v
    RQ Worker
        |
        v
   Extract Text
        |
        v
    Chunking
        |
        v
 Generate Embeddings
        |
        v
 PostgreSQL + pgvector
        |
        v
 Similarity Search
        |
        v
 Relevant Context
        |
        v
    Ollama
        |
        v
   AI Response
```

### Web Search Flow

```text
User enables Web Search
        |
        v
    FastAPI
        |
        v
   Tavily Search
        |
        v
  Search Results
        |
        v
  Build Web Context
        |
        v
    AI Model
        |
        v
  Answer with Sources
```

---

## 🛠️ Technology Stack

| Category | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript |
| Backend | Python, FastAPI, WebSockets |
| Database | PostgreSQL, SQLAlchemy |
| Vector Database | pgvector |
| Migrations | Alembic |
| Authentication | JWT |
| AI Inference | Ollama, Qwen |
| Web Search | Tavily |
| Image Understanding | Gemini Vision |
| Image Hosting | Cloudinary |
| Background Jobs | Redis, RQ |
| Infrastructure | Docker, Docker Compose |
| Testing | Pytest |
| CI/CD | GitHub Actions |
| Monitoring | Sentry |

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
│   ├── web_search.py
│   ├── alembic.ini
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

## ⚙️ Local Development Setup

### Prerequisites

Install the following:

- Python 3.12
- Node.js 22
- PostgreSQL with pgvector support
- Redis
- Ollama
- Docker Desktop
- Git

### 1. Clone the repository

```powershell
git clone https://github.com/kachi-24/realtime-ai-chat.git
cd realtime-ai-chat
```

### 2. Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install backend dependencies

```powershell
cd backend
pip install -r requirements.txt
```

### 4. Configure environment variables

Create your local `.env` configuration using the environment variables required by the backend and frontend.

Configuration includes:

- PostgreSQL connection.
- Redis connection.
- JWT authentication.
- Email verification.
- Ollama.
- Tavily web search.
- Cloudinary.
- Gemini Vision.
- Sentry.
- Frontend API and WebSocket URLs.

See the Environment Variables section below.

**Never commit `.env` files, API keys, or private credentials to GitHub.**

### 5. Start Ollama

Install Ollama and download the configured model:

```powershell
ollama pull qwen3:1.7b
```

Check installed models:

```powershell
ollama list
```

### 6. Start the backend

From the `backend` directory:

```powershell
uvicorn main:app --reload --port 8000
```

### 7. Start the frontend

Open another terminal:

```powershell
cd realtime-ai-chat/frontend
npm install
npm run dev
```

### 8. Start Docker services

From the directory containing `docker-compose.yaml`:

```powershell
docker compose up --build
```

Stop the Compose-managed services:

```powershell
docker compose down
```

**Do not use `docker compose down -v` unless you intentionally want to remove volumes and their stored data.**

Make sure PostgreSQL and Redis are running and that the connection URLs match your selected local or Docker configuration.

---

## 🔑 Environment Variables

The following are configuration examples. Use the actual variable names expected by your application code.

### Backend

```env
DATABASE_URL=
REDIS_URL=

JWT_SECRET_KEY=
ACCESS_TOKEN_EXPIRE_MINUTES=
REFRESH_TOKEN_EXPIRE_DAYS=

RESEND_API_KEY=
EMAIL_FROM=

OLLAMA_URL=
OLLAMA_MODEL=

TAVILY_API_KEY=

CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

GEMINI_API_KEY=

SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=
```

### Frontend

```env
VITE_API_URL=
VITE_WS_URL=
VITE_ENVIRONMENT=

VITE_SENTRY_DSN=
VITE_SENTRY_TRACES_SAMPLE_RATE=
```

Do not publish real environment variable values.

---

## 🧪 Testing

### Backend tests

```powershell
cd backend
pytest -q
```

### Python syntax check

```powershell
python -m compileall .
```

### Frontend production build

```powershell
cd frontend
npm ci
npm run build
```

---

## 🔁 CI/CD — GitHub Actions

The project uses GitHub Actions to automatically validate backend and frontend changes.

The CI workflow supports:

- Pushes to `main`.
- Pushes to `develop`.
- Pushes to feature branches matching `feature/**`.
- Pull requests targeting `main` and `develop`.

### Backend CI

```text
Checkout Repository
        |
        v
Set Up Python 3.12
        |
        v
Install Dependencies
        |
        v
Compile Python Files
        |
        v
Run Pytest
```

### Frontend CI

```text
Checkout Repository
        |
        v
Set Up Node.js
        |
        v
Install Dependencies
        |
        v
npm ci
        |
        v
npm run build
```

This helps detect errors before changes are merged into the main branch.

---

## 🔒 Security Considerations

The application incorporates:

- Password hashing.
- JWT authentication.
- Refresh-token authentication.
- Email verification.
- Protected WebSocket connections.
- User-level resource isolation.
- Rate limiting.
- CORS restrictions.
- Environment-based secrets.
- Sentry error monitoring.

For production deployment, additional security measures should include HTTPS, secure cookie configuration, managed secrets, database access restrictions, and production-grade monitoring.

---

## 📈 Distributed Systems Concepts

This project demonstrates practical distributed-systems concepts.

### Stateless API
JWT-based authentication supports API instances that do not need to maintain individual session state.

### Redis
Redis provides shared infrastructure for rate limiting, caching, and background job communication.

### Background Workers
RQ separates document-processing workloads from the main API server, allowing worker capacity to be scaled independently.

### WebSockets
WebSockets provide persistent, real-time communication between the frontend and backend.

For multi-instance deployments, shared WebSocket coordination would require infrastructure such as Redis Pub/Sub or another message broker.

### Database and Vector Search
PostgreSQL provides persistent storage, while pgvector supports similarity-based retrieval.

---

## 🚧 Development Status

The project includes the following implemented areas:

- [x] React frontend
- [x] FastAPI backend
- [x] WebSocket chat
- [x] Ollama local inference
- [x] PostgreSQL
- [x] Redis
- [x] RQ background jobs
- [x] Document upload
- [x] RAG pipeline
- [x] pgvector similarity search
- [x] JWT authentication
- [x] Refresh tokens
- [x] Email verification
- [x] User-level data isolation
- [x] Rate limiting
- [x] Voice-to-text
- [x] Automatic conversation titles
- [x] Feature flags
- [x] Sentry integration
- [x] Web search integration
- [x] Image understanding integration
- [x] Docker support
- [x] GitHub Actions CI workflow

---

## 🛣️ Future Improvements

Potential improvements include:

- Horizontal backend scaling.
- Redis Pub/Sub for multi-instance WebSocket communication.
- Production GPU inference infrastructure.
- Model load balancing.
- Object storage for uploaded documents.
- Database connection pooling and read replicas.
- Advanced RAG evaluation.
- Hybrid keyword and vector search.
- Improved RAG response evaluation.
- Production deployment.
- Infrastructure monitoring.
- Automated deployment through CI/CD.

---

## 🎯 Project Goals

The goal is to build more than a simple AI chatbot.

This project brings together:

```text
AI
+
Retrieval-Augmented Generation
+
Web Search
+
Image Understanding
+
WebSockets
+
Authentication
+
PostgreSQL
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

into one full-stack AI application.

---

## 👨‍💻 Author

**Agbo Onyedikachi**

Software Engineering Student & Developer

GitHub: [@kachi-24](https://github.com/kachi-24)

---

## 📜 License

This project is currently intended for educational and portfolio purposes.

