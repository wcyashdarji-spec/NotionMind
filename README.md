<h1 align="center">Notion Ingestion & Search Service</h1>

<p align="center">
  A FastAPI-based application and FastMCP server for recursively crawling hierarchical <strong>Notion</strong> documentation, indexing it into <strong>Zilliz Milvus</strong> as hybrid vectors, and query-answering via <strong>Pydantic AI</strong> and <strong>Google Gemini</strong>.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Latest-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/FastMCP-Server-orange.svg" alt="FastMCP">
  <img src="https://img.shields.io/badge/Pydantic_AI-Framework-E620E9.svg" alt="Pydantic AI">
  <img src="https://img.shields.io/badge/Logfire-Observability-yellow.svg" alt="Logfire">
  <img src="https://img.shields.io/badge/Milvus-Zilliz_Cloud-0052CC.svg" alt="Zilliz Milvus">
  <img src="https://img.shields.io/badge/uv-Package_Manager-purple.svg" alt="uv">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

---

## Features

- 🚀 **Recursive Notion Crawler** – Recursively traverses child pages and databases from a workspace or root page.
- 📝 **Markdown Parser** – Converts complex Notion blocks, databases, and lists into clean Markdown documentation.
- 🔍 **Hybrid Dense + Sparse Search** – Performs dual dense semantic (COSINE) and sparse keyword (BM25) searches simultaneously in Milvus.
- 🔀 **RRF Reranking** – Merges and ranks retrieval results using Reciprocal Rank Fusion (k=60).
- 🤖 **Pydantic AI Agent** – Fully integrated agent utilizing Google's Gemini models with dynamic app/collection routing.
- 🔌 **FastMCP Integration** – Standardized Model Context Protocol (MCP) server for tool registration and access.
- 🔥 **Logfire Observability** – Production-grade tracing, latency tracking, and token usage inspection for LLM calls.
- ⚙️ **Environment-based Configuration** – Fully configurable via dotenv files.
- 📝 **Structured Logging** – Detailed console and file-based tracking of crawling, search, and agent queries.

---

## Getting Started

Follow these steps to set up the project locally.

### Prerequisites

Make sure the following are installed:

- Python 3.12 or later
- Zilliz Milvus Cloud Instance
- Notion API Integration Token
- Google Gemini API Credentials
- uv (Recommended)

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

Activate the virtual environment.

**Windows**

```bash
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

### Start the FastAPI Web Service (Ingestion & Search Endpoint)

```bash
uvicorn main:app --reload --port 8000
```

### Start the FastMCP Server (stdio or streamable-http)

```bash
python mcp_server/server.py
```

---

## Configuration

Create a `.env` file in the project root.

```env
MILVUS_ENDPOINT=https://your-milvus-cluster.zilliz.com
MILVUS_TOKEN=your-milvus-token
MILVUS_COLLECTION_NAME=notion_documentation

NOTION_TOKEN=ntn_your-notion-token
GOOGLE_API_KEY=your-google-gemini-api-key
```

---

## Project Structure

```text
├── mcp_server/           # FastMCP Server implementation
│   ├── tools/            # Registered MCP tools (e.g. search_notion_docs)
│   └── server.py         # MCP server startup and health routes
├── src/
│   ├── api/              # API schemas and validation models
│   ├── config.py         # Logger setup and environment configuration
│   ├── routes/           # FastAPI routers (health, ingest, search, agent)
│   ├── services/         # Notion crawler, Milvus indexing, and Pydantic AI agent
│   └── utils/            # Shared helper functions
├── main.py               # Application entrypoint & startup handlers
├── pyproject.toml        # Project requirements and tool configuration
└── README.md             # Project documentation
```

---

## Architecture

The application follows a clean layered architecture.

- **API Layer** – Routes incoming HTTP requests (crawling triggers, hybrid search queries, agent chat queries).
- **Agent Layer** – Powered by `pydantic-ai` and Logfire, translating natural language questions into search tool runs.
- **Service Layer** – Notion SDK integrations, Markdown parsing, and Milvus vector collection query/index logic.
- **MCP Server Layer** – Standardized FastMCP server exposing tools to LLMs or clients.
- **Core Layer** – Coordinates dotenv management, Milvus connection pooling, and structured logging.

---

## Technology Stack

- Python 3.12+
- FastAPI
- FastMCP
- Pydantic AI
- Pydantic Logfire
- Zilliz Milvus
- Httpx
- python-dotenv
- sentence-transformers
- uv
- Uvicorn

---

## Logging & Observability

The application monitors vital endpoints and execution flows, including:

- Notion page and database recursive crawling progress
- Vector search latency, similarity scores, and BM25 statistics
- Google Gemini token consumption and tool call execution traces via Logfire
- Client request routes and runtime exceptions
