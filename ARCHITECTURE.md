# ContractGuard AI - Architecture Documentation

## System Overview

ContractGuard AI is a multi-agent contract intelligence platform built on Google ADK.

```mermaid
flowchart TB
    subgraph PRESENTATION["PRESENTATION LAYER"]
        WebUI[Web UI<br/>Alpine.js]
        REST[REST API<br/>FastAPI]
        WS[WebSocket<br/>Real-time]
        PROTO[A2A/MCP<br/>Protocols]
    end

    subgraph APPLICATION["APPLICATION LAYER"]
        subgraph AGENTS["MULTI-AGENT SYSTEM (Google ADK)"]
            ORCH[ORCHESTRATOR<br/>Root Agent]
            RAG[RAG Agent<br/>search, retrieve]
            RISK[Risk Agent<br/>analyze, identify]
            REPORT[Report Agent<br/>summary, extract]
            COMPARE[Compare Agent<br/>diff, compare]
        end
    end

    subgraph SERVICE["SERVICE LAYER"]
        VECTOR[Vector Service<br/>Weaviate]
        EMBED[Embedding Service<br/>Gemini]
        CHUNK[Chunking Service<br/>Clause-aware]
        STORE[Storage Service<br/>MinIO]
        SESSION[Session Service<br/>Redis]
        MEMORY[Memory Bank<br/>mem0]
    end

    subgraph INFRA["INFRASTRUCTURE LAYER"]
        WEAVIATE[(Weaviate<br/>:8080)]
        REDIS[(Redis<br/>:6379)]
        MINIO[(MinIO<br/>:9000)]
        POSTGRES[(PostgreSQL<br/>:5432)]
    end

    subgraph EXTERNAL["EXTERNAL SERVICES"]
        GEMINI[Google Gemini 2.5 Flash API<br/>LLM + Embeddings]
    end

    PRESENTATION --> APPLICATION
    ORCH --> RAG
    ORCH --> RISK
    ORCH --> REPORT
    RAG --> COMPARE
    APPLICATION --> SERVICE
    SERVICE --> INFRA
    INFRA --> EXTERNAL
```

---

## Service Endpoints & Monitoring

### Service URLs (Local Development)

| Service | URL | Purpose | Health Check |
|---------|-----|---------|--------------|
| **API** | http://localhost:8000 | Main application | `/health` |
| **Web UI** | http://localhost:8000/ | Frontend interface | N/A |
| **API Docs** | http://localhost:8000/docs | Swagger UI | N/A |
| **Metrics** | http://localhost:8000/metrics | App metrics | N/A |
| **Weaviate** | http://localhost:8080 | Vector database | `/v1/.well-known/ready` |
| **Weaviate gRPC** | localhost:50051 | gRPC interface | N/A |
| **Redis** | localhost:6379 | Sessions/cache | `PING` command |
| **MinIO API** | http://localhost:9000 | Object storage | `/minio/health/live` |
| **MinIO Console** | http://localhost:9001 | Storage UI | N/A |
| **PostgreSQL** | localhost:5432 | Metadata DB | `pg_isready` |

### Health Check Commands

```bash
# Check all services at once
make health

# Individual service checks
curl http://localhost:8000/health                    # API
curl http://localhost:8080/v1/.well-known/ready      # Weaviate
curl http://localhost:9000/minio/health/live         # MinIO
docker compose -f deploy/docker-compose.yml exec redis redis-cli ping    # Redis
docker compose -f deploy/docker-compose.yml exec postgres pg_isready -U postgres  # PostgreSQL
```

### Metrics Endpoint

```bash
# Get application metrics
curl http://localhost:8000/metrics
```

Returns:
```json
{
  "agents": { ... },
  "tools": { ... },
  "queries": {
    "count": 10,
    "avg_duration_ms": 2500.5,
    "min_duration_ms": 1200,
    "max_duration_ms": 5000,
    "errors": 0
  }
}
```

---

## Agent System (Google ADK)

### Agent Hierarchy

```mermaid
flowchart TD
    ORCH[ORCHESTRATOR AGENT<br/>Routes queries to sub-agents]

    ORCH --> RAG
    ORCH --> RISK
    ORCH --> REPORT

    subgraph RAG_BOX["RAG AGENT"]
        RAG[search<br/>context<br/>list]
    end

    subgraph RISK_BOX["RISK AGENT"]
        RISK[search<br/>identify<br/>analyze]
    end

    subgraph REPORT_BOX["REPORT AGENT"]
        REPORT[search<br/>extract<br/>summary]
    end

    RAG --> COMPARE

    subgraph COMPARE_BOX["COMPARE AGENT"]
        COMPARE[compare<br/>diff]
    end
```

### Google ADK Integration

```python
# Orchestrator with sub-agents
orchestrator = Agent(
    name="contractguard_orchestrator",
    model=LiteLlm(model="gemini/gemini-2.0-flash-exp"),
    instruction=ORCHESTRATOR_INSTRUCTION,
    sub_agents=[rag_agent, risk_agent, compare_agent, report_agent],
)
```

### Agent Responsibilities

| Agent | Primary Role | Tools Used |
|-------|--------------|------------|
| **Orchestrator** | Route requests, coordinate sub-agents | N/A (delegates) |
| **RAG Agent** | Document search, Q&A | search_contracts, get_contract_context |
| **Risk Agent** | Risk identification | search_contracts, identify_risks, analyze_clause |
| **Compare Agent** | Contract comparison | get_contract_context, generate_comparison_report |
| **Report Agent** | Report generation | extract_obligations, generate_summary, generate_risk_report |

---

## Data Processing Pipeline

### Document Ingestion

```mermaid
flowchart LR
    subgraph INGEST["Document Ingestion Pipeline"]
        UPLOAD[Upload PDF] --> PARSE[Parse<br/>pypdf]
        PARSE --> CHUNK[Chunk<br/>Clause-aware]
        CHUNK --> EMBED[Embed<br/>Gemini]
        EMBED --> WEAVIATE[(Store<br/>Weaviate)]
        WEAVIATE --> INDEX[Index Vectors<br/>HNSW]
    end

    UPLOAD --> MINIO[(Store Original<br/>MinIO)]
    MINIO --> POSTGRES[(Save Metadata<br/>PostgreSQL)]
```

### Query Processing

```mermaid
flowchart LR
    subgraph QUERY["Query Processing Pipeline"]
        INPUT[User Query] --> SESSION[Session<br/>Redis]
        SESSION --> ORCH[Orchestrator]
        ORCH --> AGENT[Sub-Agent]
        AGENT --> TOOLS[Tools Execute]
        TOOLS --> SEARCH[(Vector Search<br/>Weaviate)]
        SEARCH --> CONTEXT[Context]
        CONTEXT --> LLM[LLM<br/>Gemini]
        LLM --> RESPONSE[Response]
    end
```

### Clause-Aware Chunking

```python
# Detects legal document structure
CLAUSE_PATTERN = r'^(\d+\.(?:\d+\.)*)\s*(.+?)(?:\n|$)'
SECTION_PATTERN = r'^(?:ARTICLE|SECTION|Part)\s+(\d+|[IVX]+)[:\.]?\s*(.+?)(?:\n|$)'

# Preserves:
# - Clause numbers (5.1, 5.1.1, etc.)
# - Section hierarchy
# - Context relationships
```

---

## Session & Memory Architecture

```mermaid
flowchart TB
    USER[User] --> SERVICE

    subgraph SERVICE["SESSION SERVICE"]
        CREATE[create_session]
        ADD[add_message]
        GET[get_context]
        TTL[TTL: 24 hours]
    end

    subgraph REDIS["REDIS STORAGE"]
        SESSION["session:{id}<br/>user_id, created_at, documents"]
        HISTORY["history:{id}<br/>role, content, timestamp"]
        CACHE["cache:{key}<br/>cached_data"]
    end

    CREATE --> SESSION
    ADD --> HISTORY
    GET --> HISTORY
```

---

## A2A Protocol Integration

```mermaid
sequenceDiagram
    participant Client as Remote Agent Client
    participant Server as ContractGuard A2A Server
    participant Agent as Agent System

    Client->>Server: GET /.well-known/agent.json
    Server-->>Client: Agent Card (skills)

    Client->>Server: POST /a2a/tasks<br/>{skillId: "contract_search", input}
    Server->>Agent: Dispatch to Agent
    Agent-->>Server: Result
    Server-->>Client: Task Result
```

**Agent Card Skills:**

| Skill | Description |
|-------|-------------|
| `contract_search` | Semantic search |
| `risk_analysis` | Risk identification |
| `contract_comparison` | Compare contracts |
| `report_generation` | Generate reports |
| `document_ingestion` | Upload documents |
| `contract_qa` | Q&A about contracts |

---

## MCP Integration

```mermaid
sequenceDiagram
    participant Client as MCP Client<br/>(Claude, etc)
    participant Server as ContractGuard MCP Server

    Client->>Server: GET /mcp/tools
    Server-->>Client: [list of tools]

    Client->>Server: POST /mcp/tools/search_contracts<br/>{query: "...", top_k: 5}
    Server-->>Client: Tool execution result
```

**Exposed MCP Tools:**

| Tool | Description |
|------|-------------|
| `search_contracts` | Vector search |
| `analyze_risk` | Risk analysis |
| `compare_contracts` | Comparison |
| `generate_report` | Summaries |
| `extract_clauses` | Clause extraction |

---

## Google ADK Native Features

### Long-Running Operations

Google ADK provides native support through:

| ADK Feature | Description |
|-------------|-------------|
| `Runner.run_async()` | Async execution for non-blocking operations |
| Streaming callbacks | Real-time response streaming |
| Session state | State maintained across interactions |

Our additions for enterprise persistence:
- **Redis persistence** - Session state survives server restarts
- **WebSocket updates** - Real-time progress to frontend
- **Task queue** - Background processing for large documents

### FunctionTools

```python
# Tools are automatically derived from function signature
search_contracts_tool = FunctionTool(func=search_contracts)
```

Each tool:
1. Receives parameters from the agent
2. Executes business logic (embedding, search, analysis)
3. Returns structured results
4. Includes tracing via OpenTelemetry

---

## Database Architecture (Future-Ready)

### Current MVP Data Flow

```mermaid
flowchart LR
    PDF[PDF Upload] --> MINIO[(MinIO<br/>File Storage)]
    PDF --> WEAVIATE[(Weaviate<br/>Embeddings + Metadata)]
    QUERY[User Query] --> REDIS[(Redis<br/>Session State)]
```

### PostgreSQL Schema (Prepared for Future Features)

The PostgreSQL database has tables defined but **not actively used** in the current MVP:

| Table | Schema | Future Purpose |
|-------|--------|----------------|
| **users** | id, email, role, preferences | User authentication, RBAC |
| **documents** | id, filename, status, user_id | Document ownership, audit trails |
| **sessions** | id, user_id, session_data | Persistent conversation history |

**Why tables exist but aren't used:**
- **MVP Focus**: The current implementation prioritizes agent functionality over user management
- **Future-Proofing**: Schema is ready for authentication, multi-tenancy, and audit logging
- **Separation of Concerns**: Weaviate handles vectors, MinIO handles files, Redis handles sessions

**Current data storage:**
- **PDFs** → MinIO (S3-compatible object storage)
- **Embeddings + Metadata** → Weaviate (vector database)
- **Sessions** → Redis (fast key-value store with TTL)
- **PostgreSQL** → Schema defined, ready for user features

---

## Deployment Architecture

### Local Development

```mermaid
flowchart TB
    subgraph DOCKER["docker-compose.yml"]
        WEAVIATE[(Weaviate<br/>:8080)]
        REDIS[(Redis<br/>:6379)]
        MINIO[(MinIO<br/>:9000/01)]
        POSTGRES[(PostgreSQL<br/>:5432)]
    end

    subgraph UVICORN["uvicorn (make dev)"]
        FASTAPI["FastAPI Server :8000<br/>hot-reload enabled"]
        WEB["/ - Web UI"]
        DOCS["/docs - API Docs"]
        HEALTH["/health - Health Check"]
        METRICS["/metrics - Metrics"]
    end

    DOCKER --> UVICORN
```

### Production (Cloud Run)

```mermaid
flowchart TB
    subgraph GCP["GOOGLE CLOUD PLATFORM"]
        subgraph CLOUDRUN["CLOUD RUN"]
            CONTAINER[ContractGuard API Container<br/>Auto-scaling: 0-10<br/>Memory: 2GB, CPU: 2]
        end

        WEAVIATE[(Weaviate Cloud)]
        MEMSTORE[(Memorystore<br/>Redis)]
        STORAGE[(Cloud Storage)]
        CLOUDSQL[(Cloud SQL<br/>PostgreSQL)]
    end

    CLOUDRUN --> WEAVIATE
    CLOUDRUN --> MEMSTORE
    CLOUDRUN --> STORAGE
    CLOUDRUN --> CLOUDSQL
```

---

## Observability

### Tracing (OpenTelemetry)

```mermaid
flowchart TD
    ORCH[agent.orchestrator]
    RAG[agent.rag_agent]
    SEARCH[tool.search_contracts]
    EMBED[embed_query]
    VECTOR[vector_search]
    SUMMARY[tool.generate_summary]

    ORCH --> RAG
    ORCH --> SUMMARY
    RAG --> SEARCH
    SEARCH --> EMBED
    SEARCH --> VECTOR
```

### Logging (structlog)

```json
{
  "event": "Search completed",
  "result_count": 5,
  "top_score": 0.92,
  "agent": "rag",
  "timestamp": "2024-11-14T10:30:00Z"
}
```

### Metrics Collection

The `/metrics` endpoint provides:
- Query counts and latencies
- Agent invocation statistics
- Tool usage tracking
- Error rates

---

## File Structure (Active Files)

```
src/
├── main.py              ◀── Entry point, routes, lifespan
├── config.py            ◀── Environment settings
│
├── agents/
│   ├── __init__.py      ◀── Agent exports, run_agent helper
│   ├── orchestrator.py  ◀── Root agent, sub-agent routing
│   ├── rag_agent.py     ◀── Document retrieval
│   ├── risk_agent.py    ◀── Risk analysis
│   ├── compare_agent.py ◀── Contract comparison
│   └── report_agent.py  ◀── Report generation
│
├── tools/
│   ├── search_tool.py   ◀── Vector search
│   ├── analysis_tool.py ◀── Clause analysis
│   ├── report_tool.py   ◀── Report tools
│   └── google_search_tool.py ◀── Web search
│
├── services/
│   ├── vector_service.py    ◀── Weaviate ops
│   ├── embedding_service.py ◀── Gemini embeddings
│   ├── chunking_service.py  ◀── Clause-aware chunking
│   └── storage_service.py   ◀── MinIO ops
│
├── memory/
│   ├── session_service.py   ◀── Redis sessions
│   └── memory_bank.py       ◀── Long-term memory
│
├── a2a/
│   ├── agent_card.py    ◀── Agent capabilities
│   ├── server.py        ◀── A2A endpoints
│   └── client.py        ◀── A2A client
│
├── mcp/
│   ├── toolset.py       ◀── MCP tool manager
│   └── server.py        ◀── MCP endpoints
│
├── api/
│   ├── websocket.py     ◀── Real-time updates
│   ├── tasks.py         ◀── Task management
│   └── evaluation.py    ◀── Eval endpoints
│
├── models/
│   ├── user.py          ◀── User model
│   └── document.py      ◀── Document model
│
├── core/
│   ├── database.py      ◀── PostgreSQL
│   └── redis_client.py  ◀── Redis utils
│
├── evaluation/
│   ├── evaluator.py     ◀── LLM-as-judge
│   └── test_cases.py    ◀── Test suites
│
└── observability/
    ├── logger.py        ◀── Structured logging
    ├── tracer.py        ◀── OpenTelemetry
    └── metrics.py       ◀── Metrics collection

frontend/
├── templates/
│   └── index.html       ◀── Web UI (Alpine.js + Tailwind)
├── static/
│   └── .gitkeep
└── README.md
```
