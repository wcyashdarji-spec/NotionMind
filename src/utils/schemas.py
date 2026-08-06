from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for user registration."""
    email: EmailStr = Field(..., description="A valid e-mail address for the new account.")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters).")


class LoginRequest(BaseModel):
    """Request body for user login."""
    email: EmailStr = Field(..., description="Registered e-mail address.")
    password: str = Field(..., description="Account password.")


class TokenResponse(BaseModel):
    """Response body returned after a successful login."""
    access_token: str = Field(..., description="Signed JWT Bearer token.")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer').")
    expires_in: int = Field(..., description="Token lifetime in seconds.")


class UserResponse(BaseModel):
    """Public user profile returned by /auth/me."""
    id: int
    email: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


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
        description="Target Chroma collection name. Falls back to CHROMA_COLLECTION_NAME env var.",
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
        description="Chroma collection to search. Falls back to CHROMA_COLLECTION_NAME env var.",
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
        description="Target Chroma collection name. Falls back to CHROMA_COLLECTION_NAME env var.",
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


class UpdateAllRequest(BaseModel):
    """Request body for updating all collection contents."""

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


class UpdateAllResponse(BaseModel):
    """Response body for updating all collections."""

    status: str = Field(..., description="Overall status of the bulk update operation.")
    updated_collections: list[UpdateResponse] = Field(..., description="Details of each updated collection.")
    message: str = Field(..., description="Summary message of the run.")


class DeleteCollectionResponse(BaseModel):
    """Response body for the collection deletion endpoint."""

    status: str = Field(..., description="Status of the deletion operation (always 'success').")
    collection_name: str = Field(..., description="The name of the deleted collection.")
    message: str = Field(..., description="Details about the deleted resource counts.")


class TokenGenerateRequest(BaseModel):
    collection_name: str = Field(..., description="The name of the collection to generate the token for.")
    expires_days: int = Field(30, description="Expiration period in days. Must be 30, 60, or 90.")


class TokenGenerateResponse(BaseModel):
    id: int
    token: str
    collection_name: str
    duration_days: int
    is_valid: bool
    created_at: str
    expires_at: str


class TokenListItem(BaseModel):
    id: int
    token: str
    collection_name: str
    duration_days: int
    is_valid: bool
    created_at: str
    expires_at: str