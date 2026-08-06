<h1 align="center">Notion Ingestion & Search Service</h1>

<p align="center">
  A FastAPI-based application and FastMCP server for recursively crawling hierarchical <strong>Notion</strong> documentation, downloading/serving image assets, indexing them into <strong>ChromaDB</strong> as semantic vectors, and answering queries via <strong>Pydantic AI</strong> and <strong>Google Gemini</strong>.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Latest-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/FastMCP-Server-orange.svg" alt="FastMCP">
  <img src="https://img.shields.io/badge/Pydantic_AI-Framework-E620E9.svg" alt="Pydantic AI">
  <img src="https://img.shields.io/badge/Logfire-Observability-yellow.svg" alt="Logfire">
  <img src="https://img.shields.io/badge/ChromaDB-Vector_Store-009688.svg" alt="ChromaDB">
  <img src="https://img.shields.io/badge/uv-Package_Manager-purple.svg" alt="uv">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

---

## Features

- 🚀 **Recursive Notion Crawler** – Recursively traverses child pages and databases from a workspace or root page.
- 📝 **Markdown Parser** – Converts complex Notion blocks, lists, and tables into clean Markdown documentation.
- 🖼️ **Multimodal Asset Pipeline** – Extracts inline/cover images from Notion pages, downloads them to local storage, mounts them statically via FastAPI, and indexes them.
- 🔍 **Semantic Vector Search** – Queries local ChromaDB collection using high-quality semantic vector similarity.
- 🧠 **CLIP Multimodal Embeddings** – Employs OpenAI CLIP (with sentence-transformers text fallback) to generate synchronized cross-modal embeddings for text chunks and page images.
- 🤖 **Pydantic AI Agent** – Fully integrated RAG agent utilizing Google's Gemini models with dynamic tool routing.
- 🔌 **FastMCP Integration** – Standardized Model Context Protocol (MCP) server for tool registration (`search_notion_docs`) and remote LLM access.
- 🔐 **JWT Authentication & Session Management** – Provides endpoint-level protection via user registration, login, token refresh, and absolute logout with token revocation blacklists.
- ⚙️ **Utility-wise Collection Access Control** – Restricts collection access in FastMCP server using JWT Bearer tokens scoped to specific collections.
- 🗑️ **Collection Deletion API** – Cleanly purges any collection from ChromaDB, including all associated text chunks, database ingestion records, and downloaded local image assets.
- 🔥 **Logfire Observability** – Production-grade tracing, latency tracking, and token usage inspection for LLM calls.

---

## Getting Started

Follow these steps to set up the project locally.

### Prerequisites

Make sure the following are installed:

- Python 3.12 or later
- Notion API Integration Token
- Google Gemini API Credentials
- PostgreSQL or SQLite database
- **uv** (Recommended package manager)

Install **uv** if you don't already have it:

```bash
pip install uv
```

---

## Installation

### Clone the Repository

```bash
git clone <repository-url>
cd notion-ingestion
```

### Create a Virtual Environment

```bash
uv venv
```

Activate the virtual environment:

**Windows (PowerShell)**
```powershell
.venv\Scripts\activate
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

### Install Dependencies

```bash
uv sync
```

---

## Running the Application

### Start the FastAPI Web Service (API Gateway)

```bash
uvicorn main:app --reload --port 8000
```
This runs the web server at `http://localhost:8000` and mounts static files (e.g. images) under `/static`.

### Start the FastMCP Server

```bash
python mcp_server/server.py
```
- **Stdio Transport**: If spawned inside a non-TTY terminal (like inside Cursor or Claude Desktop app config), it automatically runs in stdio transport mode.
- **HTTP Transport**: If run in a standard TTY terminal, it starts as a streamable HTTP server listening on `http://0.0.0.0:8001/mcp` with health checks mounted at `/mcp/health`.

---

## API Endpoints

All protected endpoints require a JWT token in the `Authorization: Bearer <token>` header, obtained via `/auth/login`.

### Authentication
- `POST /auth/register` – Registers a new user account (hashes password using bcrypt).
- `POST /auth/login` – Authenticates user credentials and returns a 60-minute JWT token.
- `POST /auth/logout` – Revokes the current active token by blacklisting its JTI.
- `GET /auth/me` – Returns the logged-in user profile.

### Ingestion & Maintenance
- `POST /api/ingest` – Crawls Notion pages, parses layout, and indexes text and images into ChromaDB.
  - **Body parameters**:
    - `root_id` *(optional)*: Root page/database UUID to crawl. If omitted, crawls the entire workspace.
    - `collection_name` *(optional)*: Target Chroma collection name.
    - `recreate` *(optional, bool)*: If `true`, wipes existing collection before inserting new data.
- `POST /api/update` – Re-crawls Notion, recreates the collection, and indexes fresh chunks.
- `POST /api/update-all` – Bulk-updates all registered Notion collections stored in the database.
- `GET /api/records` – Lists all database ingestion records tracked in PostgreSQL.
- `DELETE /api/collection/{collection_name}` – Purges the collection from ChromaDB, deletes all associated local image files, and removes the ingestion metadata from the PostgreSQL database.

### Search & Agent
- `POST /api/search` – Queries the vector database using dense semantic vectors.
- `POST /api/agent/chat` – Prompts the Pydantic AI Notion Agent with dynamic collection/app routing.

### System Logs & Health
- `GET /api/logs` – Tails the most recent application log lines (up to 1000 lines).
- `GET /api/health` – Returns configuration status for Notion and local ChromaDB.

---

## Collection Authorization & Token Generation

The FastMCP server enforces **utility-wise collection access control** using JWT Bearer tokens. Each token defines an authorized collection scope (e.g. `Rivyo_docs` or `Editly_Order_Editing_App`). A token scoped for `Rivyo_docs` cannot access `Editly_Order_Editing_App` and vice-versa.

### Generate a Bearer Token

Run the included token generator script:

```bash
# Generate token scoped for Rivyo_docs (valid for 30 days)
python scripts/generate_token.py --collection Rivyo_Docs

# Generate token scoped for multiple collections with 60-day expiry
python scripts/generate_token.py --collection Rivyo_Docs Editly_Order_Editing_App --expires-days 60
```

### Passing Token to MCP Tools

Tokens can be passed via the `token` argument in MCP tool calls (`search_notion_docs`) or as a standard HTTP `Authorization: Bearer <token>` header when connecting to the HTTP FastMCP server.

---

## Configuration

Create a `.env` file in the project root containing the following variables:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/notion_db
NOTION_TOKEN=ntn_your-notion-token
GOOGLE_API_KEY=your-google-gemini-api-key
GEMINI_MODEL=google:gemini-2.5-flash

# Chroma Config
CHROMA_DB_PATH=./chroma_db
CHROMA_COLLECTION_NAME=notion_documentation
EMBEDDING_MODEL_NAME=openai/clip-vit-base-patch32

# Security Config
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
CRON_SECRET_KEY=your-cron-secret-key-here

# Optional LangSmith Tracing
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your-langsmith-api-key-here
LANGSMITH_PROJECT=Notion-MCP-Server
```

---

## Project Structure

```text
├── chroma_db/            # Local Chroma vector database storage
├── logs/                 # Application run logs directory
│   └── app.log           # Active application log file
├── static/
│   └── images/           # Crawled page image files served statically
├── mcp_server/           # FastMCP Server implementation
│   ├── tools/            # Registered MCP tools (e.g. search_notion_docs)
│   └── server.py         # MCP server startup and health routes
├── scripts/              # Helper scripts (e.g. token generation)
├── src/
│   ├── config.py         # Logger setup and environment configuration
│   ├── database/         # Database connections, models, and crud operations
│   ├── routes/           # FastAPI routers (health, ingest, search, agent, logs, auth)
│   ├── services/         # Notion crawler, Chroma indexing, agent, and CLIP service
│   └── utils/            # JWT auth, text chunking, dependency injection, and schemas
├── main.py               # Application entrypoint & startup handlers
├── pyproject.toml        # Project requirements and tool configuration
└── README.md             # Project documentation
```

---

## Architecture

The application follows a clean layered architecture:

- **API Layer (FastAPI)** – Routes incoming HTTP requests (crawling, updates, deletions, hybrid search, auth sessions).
- **Agent Layer (Pydantic AI)** – Powered by Google Gemini and Logfire, translating natural language questions into search tools.
- **Service Layer** – Notion API client, Markdown block parser, local image downloader, and ChromaDB vector service.
- **MCP Server Layer (FastMCP)** – Standardized server exposing tools to LLM interfaces/clients.
- **Data Layer (PostgreSQL & SQL Alchemy)** – Persists active user profiles, token revocation blacklists, and collection ingestion records.

---

## Technology Stack

- **Core**: Python 3.12+, FastAPI, FastMCP, Uvicorn
- **AI/LLM**: Pydantic AI, Google Gemini API
- **Vector Database**: ChromaDB (with local storage)
- **Embeddings**: Sentence-Transformers, OpenAI CLIP (via Pillow & Hugging Face)
- **Database**: PostgreSQL / SQLite (via SQLAlchemy)
- **Security**: PyJWT, passlib (bcrypt)
- **Observability**: Pydantic Logfire, LangSmith
- **Tooling**: uv, python-dotenv, httpx

---

## Logging & Observability

The application monitors vital endpoints and execution flows, including:
- Notion page and database recursive crawling progress and errors.
- ChromaDB indexing counts (text chunks + image blocks) and retrieval latency.
- Google Gemini token consumption and tool call execution traces via Logfire.
- User authentication events, active JWT session revoking, and token access validation.
- Disk usage and clean file deletion metrics during collection teardown.
