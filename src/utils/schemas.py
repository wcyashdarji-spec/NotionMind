from typing import Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """Request body for the agent chat endpoint."""
    prompt: str = Field(..., description="The query/message prompt for the Pydantic AI agent.")
    attribute: str = Field(..., description="The app/attribute name (e.g. 'Rivyo' or 'Editly').")

class ChatResponse(BaseModel):
    """Response body for the agent chat endpoint."""
    prompt: str
    attribute: str
    response: str

class IngestRequest(BaseModel):
    """Request body for the ingestion endpoint."""

    root_id: Optional[str] = Field(
        default=None,
        description=(
            "UUID of the root Notion page or database to crawl. "
            "When omitted the entire workspace is scanned."
        ),
    )
    collection_name: Optional[str] = Field(
        default=None,
        description="Target Milvus collection name. Falls back to MILVUS_COLLECTION_NAME env var.",
    )
    recreate: bool = Field(
        default=False,
        description="Drop and recreate the collection before inserting new data.",
    )


class SearchRequest(BaseModel):
    """Request body for the vector search endpoint."""

    query: str = Field(..., description="Natural-language query string.")
    collection_name: Optional[str] = Field(
        default=None,
        description="Milvus collection to search. Falls back to MILVUS_COLLECTION_NAME env var.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum number of results to return.",
    )

class UpdateRequest(BaseModel):
    """Request body for updating collection content."""

    root_id: Optional[str] = Field(
        default=None,
        description=(
            "UUID of the root Notion page or database to crawl for update. "
            "When omitted the entire workspace is scanned."
        ),
    )
    collection_name: Optional[str] = Field(
        default=None,
        description="Target Milvus collection name. Falls back to MILVUS_COLLECTION_NAME env var.",
    )
    chunk_size: int = Field(
        default=2000,
        ge=100,
        le=10000,
        description="Max character count per text chunk.",
    )
    chunk_overlap: int = Field(
        default=500,
        ge=0,
        le=2000,
        description="Overlap character count between consecutive chunks.",
    )


class IngestResponse(BaseModel):
    """Response body for the ingestion endpoint."""

    status: str = Field(..., description="Status of the ingestion operation.")
    root_id: Optional[str] = Field(None, description="Root Notion page/database UUID crawled.")
    collection_name: str = Field(..., description="Target collection name.")
    pages_ingested: int = Field(..., description="Number of Notion pages processed.")
    vector_chunks_created: int = Field(..., description="Total vector chunks indexed.")
    created_at: Optional[str] = Field(None, description="Timestamp when the collection record was created in Postgres.")
    updated_at: Optional[str] = Field(None, description="Timestamp when the collection record was last updated in Postgres.")


class UpdateResponse(BaseModel):
    """Response body for the collection content update endpoint."""

    status: str = Field(..., description="Status of the update operation.")
    root_id: Optional[str] = Field(None, description="Root Notion page/database UUID crawled.")
    pages_ingested: int = Field(..., description="Number of Notion pages processed.")
    vector_chunks_created: int = Field(..., description="Total vector chunks indexed.")
    collection_name: str = Field(..., description="Target collection updated.")
    message: str = Field(..., description="Summary message.")
    created_at: Optional[str] = Field(None, description="Timestamp when the collection record was created in Postgres.")
    updated_at: Optional[str] = Field(None, description="Timestamp when the collection record was last updated in Postgres.")
