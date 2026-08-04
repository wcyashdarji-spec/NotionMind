from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.config import logger
from src.utils.deps import get_current_token
from src.services.agent_service import ask_agent
from src.utils.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Query the Pydantic AI Notion Agent",
    response_description="The response from the agent powered by Google Gemini, using Notion documentation tools.",
)
async def chat(
    request: ChatRequest,
    _token: dict = Depends(get_current_token),
) -> ChatResponse:
    """
    Handle a chat request and return the AI-generated response.

    The endpoint combines the provided application attribute and user query
    into a single prompt, sends it to the configured Pydantic AI agent, and
    returns the generated response.

    Args:
        request: The incoming chat request containing the application
            attribute and the user's prompt.

    Returns:
        A `ChatResponse` containing the original prompt, attribute, and
        the agent's response.

    Raises:
        HTTPException: If an error occurs while processing the request.
    """
    try:
        logger.info(f"Received chat request: {request}")
        combined_prompt = f"App/Attribute: {request.attribute}\nUser Query: {request.prompt}"

        logger.info(f"Sending combined prompt to agent: {combined_prompt}")
        response_text = await ask_agent(combined_prompt, attribute=request.attribute)

        return ChatResponse(
            prompt=request.prompt,
            attribute=request.attribute,
            response=response_text,
        )
    except Exception as exc:
        logger.exception(f"Agent chat query failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

