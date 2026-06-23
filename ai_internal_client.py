"""Internal AI API adapter placeholder.

Company-network API code should be connected here, not inside Flask routes.
Set config.ini [AI_ASSISTANT] values like:

mode = real
real_module = ai_internal_client
real_function = ask_internal_ai
real_stream_function = ask_internal_ai_stream
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


def ask_internal_ai(question: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call the internal AI API.

    Stage 2 passes prior messages through ``context["history"]``.
    Stage 3 passes prior structured outputs through ``context["recent_results"]``.
    If this function returns ``structured_result``, ``structured_results``,
    ``result``, or ``results``, Flask stores them in ``ai_chat_results``.
    """
    return {
        "answer": (
            "사내 AI API 연결부가 아직 구현되지 않았습니다.\n"
            "회사 내부망에서 ai_internal_client.py의 ask_internal_ai 함수를 실제 API 호출로 교체하세요."
        ),
        "intent": (context or {}).get("intent", "internal_ai_placeholder"),
        "domain": (context or {}).get("domain", {}),
    }


def ask_internal_ai_stream(question: str, context: Optional[Dict[str, Any]] = None) -> Iterable[Dict[str, Any]]:
    yield {"event": "status", "message": "사내 AI API 연결부를 확인하고 있습니다."}
    result = ask_internal_ai(question, context=context)
    yield {
        "event": "meta",
        "mode": "real-placeholder",
        "intent": result.get("intent", "internal_ai_placeholder"),
        "domain": result.get("domain", {}),
    }
    yield {"event": "chunk", "text": result.get("answer", "")}
