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