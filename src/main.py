"""
ContractGuard AI - FastAPI Application

Main entry point for the ContractGuard AI API.
Provides endpoints for contract analysis using multi-agent system.
"""

import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any

import pypdf
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.a2a.server import default_a2a_server
from src.agents import create_orchestrator_agent, create_risk_agent, create_runner, run_agent
from src.api.evaluation import router as evaluation_router
from src.api.tasks import router as tasks_router
from src.api.websocket import router as websocket_router
from src.config import settings
from src.core.database import check_db_health, close_db, init_db
from src.core.redis_client import check_redis_health, close_redis
from src.mcp.server import default_mcp_server
from src.memory.memory_bank import get_memory_bank
from src.memory.session_service import get_session_manager
from src.observability.logger import get_logger, setup_logging
from src.observability.metrics import MetricsTimer, metrics_collector
from src.observability.tracer import setup_tracing
from src.services.chunking_service import ChunkingService
from src.services.embedding_service import get_embedding_service
from src.services.storage_service import get_storage_service
from src.services.vector_service import get_vector_service

setup_logging()
setup_tracing()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    logger.info("Starting ContractGuard AI", env=settings.app_env)

    vector_service = get_vector_service()
    storage_service = get_storage_service()
    session_manager = get_session_manager()

    if await vector_service.health_check():
        logger.info("Weaviate connection healthy")
    else:
        logger.warning("Weaviate not available - some features may not work")

    if await storage_service.health_check():
        logger.info("MinIO connection healthy")
        await storage_service.ensure_bucket()
    else:
        logger.warning("MinIO not available - document storage may not work")

    if await check_redis_health():
        logger.info("Redis connection healthy")
    else:
        logger.warning("Redis not available - real-time updates may not work")

    if settings.app_env == "development":
        try:
            if await check_db_health():
                await init_db()
                logger.info("PostgreSQL tables initialized")
            else:
                logger.warning("PostgreSQL not available - user features disabled")
        except Exception as e:
            logger.warning("PostgreSQL initialization skipped", error=str(e))

    yield

    logger.info("Shutting down ContractGuard AI")
    vector_service.close()
    await session_manager.close()
    await close_redis()
    try:
        await close_db()
    except Exception:
        pass


app = FastAPI(
    title="ContractGuard AI",
    description="""
    Enterprise Contract Intelligence Platform powered by Google ADK.

    Features:
    - Multi-agent contract analysis
    - Semantic search across documents
    - Risk assessment
    - Contract comparison
    - Report generation

    Built for the Kaggle Agents Intensive Capstone.
    """,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(websocket_router, prefix="/api/v1")
app.include_router(tasks_router)
app.include_router(evaluation_router)
app.include_router(default_a2a_server.router)
app.include_router(default_mcp_server.get_fastapi_router())

frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    static_path = frontend_path / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Serve the frontend application."""
        index_path = frontend_path / "templates" / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="Frontend not found")


class QueryRequest(BaseModel):
    """Request model for agent queries."""
    question: str = Field(..., description="Question to ask about contracts")
    session_id: str | None = Field(None, description="Session ID for conversation context")
    document_id: str | None = Field(None, description="Specific document to query")
    collection_name: str = Field("contracts", description="Vector collection to search")


class QueryResponse(BaseModel):
    """Response model for agent queries."""
    answer: str
    session_id: str
    sources: list[dict[str, Any]] = []
    agent_used: str | None = None


class SessionRequest(BaseModel):
    """Request model for session creation."""
    user_id: str | None = None
    document_ids: list[str] = []


class SessionResponse(BaseModel):
    """Response model for session operations."""
    session_id: str
    message: str


class AnalysisRequest(BaseModel):
    """Request model for contract analysis."""
    document_id: str = Field(..., description="Document to analyze")
    analysis_type: str = Field("general", description="Type: general, risk, legal, financial")
    session_id: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    services: dict[str, bool]


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    vector_service = get_vector_service()
    storage_service = get_storage_service()

    weaviate_healthy = await vector_service.health_check()
    minio_healthy = await storage_service.health_check()
    all_healthy = weaviate_healthy and minio_healthy

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version="0.1.0",
        services={
            "weaviate": weaviate_healthy,
            "minio": minio_healthy,
            "api": True,
        },
    )


@app.get("/metrics")
async def get_metrics():
    """Get application metrics."""
    return metrics_collector.get_summary()


@app.post("/api/v1/sessions", response_model=SessionResponse)
async def create_session(request: SessionRequest):
    """Create a new conversation session."""
    session_manager = get_session_manager()
    context = await session_manager.create_session(
        user_id=request.user_id,
        initial_documents=request.document_ids,
    )
    return SessionResponse(
        session_id=context.session_id,
        message="Session created successfully",
    )


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session information."""
    session_manager = get_session_manager()
    context = await session_manager.get_session(session_id)

    if not context:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": context.session_id,
        "user_id": context.user_id,
        "created_at": context.created_at,
        "active_documents": context.active_documents,
    }


@app.delete("/api/v1/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    session_manager = get_session_manager()
    deleted = await session_manager.delete_session(session_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session deleted"}


@app.post("/api/v1/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """Query the ContractGuard AI agent system."""
    with MetricsTimer() as timer:
        session_manager = get_session_manager()

        if request.session_id:
            context = await session_manager.get_session(request.session_id)
            if not context:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = request.session_id
        else:
            context = await session_manager.create_session()
            session_id = context.session_id

        await session_manager.add_message(session_id, "user", request.question)

        try:
            agent = create_orchestrator_agent()
            runner = create_runner(agent)

            session_context = await session_manager.get_context_for_agent(session_id)
            prompt = request.question

            if session_context.get("conversation_history"):
                prompt = f"""Previous conversation:
{session_context['conversation_history']}

Current question: {request.question}"""

            result = await run_agent(runner, prompt)
            answer = str(result) if result else "I couldn't process your question."

            await session_manager.add_message(session_id, "assistant", answer)
            metrics_collector.record_query(timer.duration_ms)

            return QueryResponse(
                answer=answer,
                session_id=session_id,
                sources=[],
                agent_used="orchestrator",
            )

        except Exception as e:
            logger.error("Query failed", error=str(e))
            metrics_collector.record_query(timer.duration_ms, error=True)
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/search")
async def search_contracts(
    query: str = Form(...),
    collection_name: str = Form("contracts"),
    top_k: int = Form(5),
):
    """Search contracts using semantic similarity."""
    embedding_service = get_embedding_service()
    vector_service = get_vector_service()

    try:
        query_vector = await embedding_service.embed_query(query)
        results = await vector_service.search(
            collection_name=collection_name,
            query_vector=query_vector,
            top_k=top_k,
        )

        return {
            "query": query,
            "results": [
                {
                    "text": r.text,
                    "score": r.score,
                    "metadata": r.metadata,
                }
                for r in results
            ],
        }

    except Exception as e:
        logger.error("Search failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze")
async def analyze_contract(request: AnalysisRequest):
    """Analyze a specific contract document."""
    try:
        agent = create_risk_agent()
        runner = create_runner(agent)

        prompt = f"""Analyze the contract with document_id: {request.document_id}

Analysis type requested: {request.analysis_type}

Please:
1. Search for the document content
2. Perform a {request.analysis_type} analysis
3. Identify key risks and concerns
4. Provide recommendations"""

        result = await run_agent(runner, prompt)

        return {
            "document_id": request.document_id,
            "analysis_type": request.analysis_type,
            "analysis": str(result),
        }

    except Exception as e:
        logger.error("Analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    collection_name: str = Form("contracts"),
    analyze_immediately: bool = Form(False),
):
    """Upload and process a contract document."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        content = await file.read()
        document_id = str(uuid.uuid4())

        storage_service = get_storage_service()
        stored_doc = await storage_service.upload_document(
            file_data=content,
            filename=file.filename,
            document_id=document_id,
            metadata={"collection": collection_name},
        )

        logger.info(
            "Document stored in MinIO",
            document_id=document_id,
            object_name=stored_doc.object_name,
        )

        pdf_reader = pypdf.PdfReader(BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"

        if not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")

        chunking_service = ChunkingService()
        chunks = chunking_service.chunk_text(
            text=text,
            document_id=document_id,
            document_name=file.filename,
        )

        embedding_service = get_embedding_service()
        texts = [c["text"] for c in chunks]
        vectors = await embedding_service.embed_documents(texts)

        vector_service = get_vector_service()

        if not await vector_service.collection_exists(collection_name):
            await vector_service.create_collection(
                collection_name=collection_name,
                vector_dimension=embedding_service.get_dimension(),
            )

        await vector_service.insert_documents(
            collection_name=collection_name,
            texts=texts,
            vectors=vectors,
            metadata_list=chunks,
        )

        logger.info(
            "Document uploaded and vectorized",
            document_id=document_id,
            filename=file.filename,
            chunks=len(chunks),
        )

        result = {
            "document_id": document_id,
            "filename": file.filename,
            "chunks": len(chunks),
            "collection": collection_name,
            "storage": {
                "object_name": stored_doc.object_name,
                "size_bytes": stored_doc.size,
            },
            "message": "Document uploaded and processed successfully",
        }

        if analyze_immediately:
            agent = create_risk_agent()
            runner = create_runner(agent)

            analysis_result = await run_agent(
                runner,
                f"Perform a quick risk assessment of document {document_id}. "
                "Identify the top 3 risks and key terms."
            )

            result["quick_analysis"] = str(analysis_result)

        return result

    except Exception as e:
        logger.error("Upload failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/documents/{document_id}")
async def get_document(
    document_id: str,
    collection_name: str = "contracts",
):
    """Get document information and content."""
    vector_service = get_vector_service()
    storage_service = get_storage_service()

    results = await vector_service.get_by_document_id(
        collection_name=collection_name,
        document_id=document_id,
    )

    if not results:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_info = await storage_service.get_document_info(document_id)
    full_text = "\n\n".join([r.text for r in results])

    return {
        "document_id": document_id,
        "chunk_count": len(results),
        "text": full_text,
        "sections": list(set(r.metadata.get("section_title", "") for r in results if r.metadata.get("section_title"))),
        "storage": {
            "object_name": storage_info.object_name if storage_info else None,
            "size_bytes": storage_info.size if storage_info else None,
            "original_filename": storage_info.metadata.get("original_filename") if storage_info else None,
        } if storage_info else None,
    }


@app.get("/api/v1/documents/{document_id}/download")
async def download_document(document_id: str):
    """Get a presigned URL to download the original PDF."""
    storage_service = get_storage_service()

    try:
        url = await storage_service.get_presigned_url(document_id)
        return {"download_url": url, "expires_in": "1 hour"}

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found in storage")


@app.get("/api/v1/documents")
async def list_documents(
    collection_name: str = "contracts",
    limit: int = 50,
):
    """List all documents in storage."""
    storage_service = get_storage_service()
    documents = await storage_service.list_documents(limit=limit)

    def get_metadata_value(metadata: dict, key: str, default: str) -> str:
        """Get metadata value handling MinIO's x-amz-meta- prefix."""
        # Try direct key
        if key in metadata:
            return metadata[key]
        # Try with x-amz-meta- prefix (MinIO convention)
        prefixed_key = f"x-amz-meta-{key}"
        if prefixed_key in metadata:
            return metadata[prefixed_key]
        # Try lowercase versions
        key_lower = key.lower()
        if key_lower in metadata:
            return metadata[key_lower]
        prefixed_lower = f"x-amz-meta-{key_lower}"
        if prefixed_lower in metadata:
            return metadata[prefixed_lower]
        return default

    return {
        "documents": [
            {
                "document_id": get_metadata_value(doc.metadata, "document_id", doc.object_name.split(".")[0]),
                "filename": get_metadata_value(doc.metadata, "original_filename", doc.object_name),
                "size_bytes": doc.size,
                "etag": doc.etag,
            }
            for doc in documents
        ],
        "total": len(documents),
    }


@app.post("/api/v1/documents/{document_id}/analyze-realtime")
async def analyze_document_realtime(
    document_id: str,
    analysis_type: str = Form("risk"),
    focus_areas: str | None = Form(None),
):
    """Real-time document analysis."""
    storage_service = get_storage_service()

    doc_info = await storage_service.get_document_info(document_id)
    if not doc_info:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        focus = f" Focus on: {focus_areas}." if focus_areas else ""
        prompt = f"""Perform a comprehensive {analysis_type} analysis on document {document_id}.{focus}

Please:
1. Search and retrieve the document content
2. Perform detailed {analysis_type} analysis
3. Identify key risks, issues, or concerns
4. Extract important terms and obligations
5. Provide actionable recommendations

Format your response with clear sections and bullet points."""

        agent = create_orchestrator_agent()
        runner = create_runner(agent)

        with MetricsTimer() as timer:
            result = await run_agent(runner, prompt)

        metrics_collector.record_agent_call("orchestrator", timer.duration_ms)

        return {
            "document_id": document_id,
            "analysis_type": analysis_type,
            "focus_areas": focus_areas.split(",") if focus_areas else None,
            "analysis": str(result),
            "duration_ms": timer.duration_ms,
            "document_info": {
                "filename": doc_info.metadata.get("original_filename"),
                "size_bytes": doc_info.size,
            },
        }

    except Exception as e:
        logger.error("Real-time analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/documents/{document_id}")
async def delete_document(
    document_id: str,
    collection_name: str = "contracts",
):
    """Delete a document from both storage and vector database."""
    vector_service = get_vector_service()
    storage_service = get_storage_service()

    storage_deleted = await storage_service.delete_document(document_id)

    return {
        "document_id": document_id,
        "storage_deleted": storage_deleted,
        "message": "Document deleted" if storage_deleted else "Document not found in storage",
    }


@app.post("/api/v1/memory")
async def add_memory(
    content: str = Form(...),
    user_id: str | None = Form(None),
):
    """Add a memory to long-term storage."""
    memory_bank = get_memory_bank()
    result = await memory_bank.add(content, user_id=user_id)
    return {"message": "Memory added", "result": result}


@app.get("/api/v1/memory/search")
async def search_memories(
    query: str,
    user_id: str | None = None,
    limit: int = 10,
):
    """Search memories semantically."""
    memory_bank = get_memory_bank()
    results = await memory_bank.search(query, user_id=user_id, limit=limit)

    return {
        "query": query,
        "results": [
            {"id": r.id, "memory": r.memory, "score": r.score}
            for r in results
        ],
    }


def main():
    """Run the application."""
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
