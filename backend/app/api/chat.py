from uuid import uuid4

from fastapi import APIRouter, Request

from app.api.deps import TodayDep
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat")
def chat(body: ChatRequest, request: Request, today: TodayDep) -> ChatResponse:
    """One conversational turn. The message is turned into a structured request, the
    deterministic engine runs it, and the reply explains the result. Nothing is saved:
    what-ifs never change the plan. Pass `thread_id` back to continue the conversation."""
    thread_id = body.thread_id or uuid4().hex
    state = request.app.state.chat_graph.invoke(
        {
            "message": body.message,
            "today": today.isoformat(),
            "default_assumption_set": body.assumption_set,
        },
        {"configurable": {"thread_id": thread_id}},
    )
    return ChatResponse(
        thread_id=thread_id,
        reply=state["reply"],
        status=state["status"],
        intent=state["intent"],
        assumption_set=state.get("assumption_set"),
        assumptions=state.get("assumptions"),
        results=state.get("results", []),
        provider=request.app.state.chat_provider.name,
    )
