"""AI query assistant routes.

The first implementation is intentionally a small mock-mode shell. It gives the
portal a stable UI/API contract now, while leaving the internal company AI
script integration as a later swap-in.
"""

import configparser
import importlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import Blueprint, Response, jsonify, render_template, request, session, stream_with_context

from config.menu import MENU_CONFIG
from db_connection import get_db_connection
from permission_helpers import enforce_permission
from timezone_config import get_korean_time


ai_assistant_bp = Blueprint("ai_assistant", __name__)

AI_ASSISTANT_MENU_CODE = "AI_ASSISTANT"
DEFAULT_MODE = "mock"
HISTORY_MESSAGE_LIMIT = 12
HISTORY_CHAR_LIMIT = 12000
RESULT_CONTEXT_LIMIT = 5

logger = logging.getLogger(__name__)


def _load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read("config.ini", encoding="utf-8")
    return config


def _get_ai_config() -> configparser.SectionProxy:
    config = _load_config()
    if not config.has_section("AI_ASSISTANT"):
        config.add_section("AI_ASSISTANT")
    return config["AI_ASSISTANT"]


def _current_login_id() -> str:
    login_id = str(
        session.get("user_id")
        or session.get("loginid")
        or session.get("login_id")
        or ""
    ).strip()
    if login_id:
        return login_id

    config = _load_config()
    sso_dev_mode = config.getboolean("SSO", "dev_mode", fallback=False)
    sso_enabled = config.getboolean(
        "SSO",
        "sso_enabled",
        fallback=config.getboolean("SSO", "enabled", fallback=True),
    )
    if sso_dev_mode or not sso_enabled:
        return config.get("SSO", "dev_user_id", fallback="dev_user").strip() or "dev_user"

    return ""


def _dt_to_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _row_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        return {}


def _session_title_from_question(question: str) -> str:
    title = " ".join((question or "").split())
    if not title:
        return "새 대화"
    return title[:40] + ("..." if len(title) > 40 else "")


def _ensure_chat_tables(conn) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_chat_sessions (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '새 대화',
            created_by_login TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT FALSE
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_chat_messages (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES ai_chat_sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_chat_results (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES ai_chat_sessions(id) ON DELETE CASCADE,
            message_id INTEGER REFERENCES ai_chat_messages(id) ON DELETE SET NULL,
            result_type TEXT NOT NULL DEFAULT 'general',
            title TEXT NOT NULL DEFAULT '',
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_chat_sessions_owner_updated
        ON ai_chat_sessions(created_by_login, updated_at DESC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_session_created
        ON ai_chat_messages(session_id, created_at ASC, id ASC)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_chat_results_session_created
        ON ai_chat_results(session_id, created_at DESC, id DESC)
        """
    )


def _serialize_chat_session(row: Any) -> Dict[str, Any]:
    data = _row_dict(row)
    return {
        "id": data.get("id"),
        "title": data.get("title") or "새 대화",
        "created_at": _dt_to_text(data.get("created_at")),
        "updated_at": _dt_to_text(data.get("updated_at")),
    }


def _serialize_chat_message(row: Any) -> Dict[str, Any]:
    data = _row_dict(row)
    metadata = data.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    return {
        "id": data.get("id"),
        "session_id": data.get("session_id"),
        "role": data.get("role"),
        "content": data.get("content") or "",
        "metadata": metadata,
        "created_at": _dt_to_text(data.get("created_at")),
    }


def _serialize_chat_result(row: Any) -> Dict[str, Any]:
    data = _row_dict(row)
    result_data = data.get("data") or {}
    metadata = data.get("metadata") or {}
    if isinstance(result_data, str):
        try:
            result_data = json.loads(result_data)
        except Exception:
            result_data = {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    return {
        "id": data.get("id"),
        "session_id": data.get("session_id"),
        "message_id": data.get("message_id"),
        "result_type": data.get("result_type") or "general",
        "title": data.get("title") or "",
        "data": result_data,
        "metadata": metadata,
        "created_at": _dt_to_text(data.get("created_at")),
    }


def _normalize_structured_results(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: List[Any] = []
    for key in ("structured_results", "results"):
        value = result.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    for key in ("structured_result", "result"):
        value = result.get(key)
        if isinstance(value, dict):
            candidates.append(value)

    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(candidates, start=1):
        if not isinstance(item, dict):
            continue
        result_type = str(
            item.get("result_type")
            or item.get("type")
            or result.get("intent")
            or "general"
        ).strip() or "general"
        title = str(item.get("title") or item.get("name") or result_type).strip()
        data = item.get("data")
        if data is None:
            data = {
                key: value
                for key, value in item.items()
                if key not in {"result_type", "type", "title", "name", "metadata"}
            }
        if not isinstance(data, (dict, list)):
            data = {"value": data}
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        normalized.append({
            "result_type": result_type,
            "title": title[:120] if title else f"result-{index}",
            "data": data,
            "metadata": metadata,
        })
    return normalized


def _load_recent_chat_history(
    conn,
    chat_session_id: int,
    limit: int = HISTORY_MESSAGE_LIMIT,
    max_chars: int = HISTORY_CHAR_LIMIT,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, session_id, role, content, metadata, created_at
          FROM ai_chat_messages
         WHERE session_id = %s
         ORDER BY created_at DESC, id DESC
         LIMIT %s
        """,
        (chat_session_id, limit),
    ).fetchall()

    messages = [_serialize_chat_message(row) for row in reversed(rows)]
    trimmed_reversed: List[Dict[str, Any]] = []
    total_chars = 0

    for message in reversed(messages):
        content = str(message.get("content") or "")
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        if len(content) > remaining:
            message = dict(message)
            message["content"] = content[-remaining:]
            content = message["content"]
        trimmed_reversed.append({
            "role": message.get("role"),
            "content": content,
            "metadata": message.get("metadata") or {},
            "created_at": message.get("created_at"),
        })
        total_chars += len(content)

    return list(reversed(trimmed_reversed))


def _get_owned_chat_session(conn, session_id: Any, login_id: str) -> Optional[Dict[str, Any]]:
    try:
        numeric_id = int(session_id)
    except (TypeError, ValueError):
        return None
    row = conn.execute(
        """
        SELECT id, title, created_at, updated_at
          FROM ai_chat_sessions
         WHERE id = %s
           AND created_by_login = %s
           AND COALESCE(is_deleted, FALSE) = FALSE
        """,
        (numeric_id, login_id),
    ).fetchone()
    return _serialize_chat_session(row) if row else None


def _create_chat_session(conn, login_id: str, title: str) -> Dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO ai_chat_sessions (title, created_by_login, created_at, updated_at, is_deleted)
        VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, FALSE)
        RETURNING id, title, created_at, updated_at
        """,
        (title or "새 대화", login_id),
    ).fetchone()
    return _serialize_chat_session(row)


def _get_or_create_chat_session(conn, login_id: str, session_id: Any, question: str) -> Tuple[Dict[str, Any], bool]:
    if session_id not in (None, "", 0, "0"):
        existing = _get_owned_chat_session(conn, session_id, login_id)
        if existing:
            return existing, False
        raise PermissionError("대화방을 찾을 수 없거나 접근 권한이 없습니다.")
    return _create_chat_session(conn, login_id, _session_title_from_question(question)), True


def _save_chat_message(
    conn,
    chat_session_id: int,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    text = content or ""
    if not text.strip():
        return None
    row = conn.execute(
        """
        INSERT INTO ai_chat_messages (session_id, role, content, metadata, created_at)
        VALUES (%s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
        RETURNING id
        """,
        (chat_session_id, role, text, json.dumps(metadata or {}, ensure_ascii=False)),
    ).fetchone()
    conn.execute(
        """
        UPDATE ai_chat_sessions
           SET updated_at = CURRENT_TIMESTAMP
         WHERE id = %s
        """,
        (chat_session_id,),
    )
    try:
        return int(row[0]) if row else None
    except Exception:
        return None


def _save_chat_results(
    conn,
    chat_session_id: int,
    message_id: Optional[int],
    result: Dict[str, Any],
) -> int:
    saved_count = 0
    for item in _normalize_structured_results(result):
        conn.execute(
            """
            INSERT INTO ai_chat_results (
                session_id, message_id, result_type, title, data, metadata, created_at
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, CURRENT_TIMESTAMP)
            """,
            (
                chat_session_id,
                message_id,
                item["result_type"],
                item["title"],
                json.dumps(item["data"], ensure_ascii=False),
                json.dumps(item["metadata"], ensure_ascii=False),
            ),
        )
        saved_count += 1
    return saved_count


def _load_recent_chat_results(
    conn,
    chat_session_id: int,
    limit: int = RESULT_CONTEXT_LIMIT,
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, session_id, message_id, result_type, title, data, metadata, created_at
          FROM ai_chat_results
         WHERE session_id = %s
         ORDER BY created_at DESC, id DESC
         LIMIT %s
        """,
        (chat_session_id, limit),
    ).fetchall()
    return [_serialize_chat_result(row) for row in rows]


def _decode_sse_event_text(event_text: str) -> Tuple[str, Dict[str, Any]]:
    event_name = "message"
    data_lines: List[str] = []
    for line in (event_text or "").splitlines():
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
    if not data_lines:
        return event_name, {}
    raw_data = "".join(data_lines)
    try:
        return event_name, json.loads(raw_data)
    except Exception:
        return event_name, {"text": raw_data}


def _get_domain_sections() -> List[Dict[str, str]]:
    config = _load_config()
    domains = []
    for section_name in config.sections():
        if not section_name.startswith("AI_DOMAIN_"):
            continue
        section = config[section_name]
        domains.append({
            "key": section_name.replace("AI_DOMAIN_", "").lower(),
            "section": section_name,
            "name": section.get("name", section_name),
            "db": section.get("db", ""),
            "description": section.get("description", ""),
            "keywords": section.get("keywords", ""),
        })
    return domains


def _match_domain(question: str, domains: List[Dict[str, str]]) -> Dict[str, str]:
    normalized = question.lower()
    best_domain = domains[0] if domains else {
        "key": "unknown",
        "name": "미분류",
        "db": "",
        "description": "",
        "keywords": "",
    }
    best_score = -1

    for domain in domains:
        keywords = [word.strip().lower() for word in domain.get("keywords", "").split(",") if word.strip()]
        score = sum(1 for word in keywords if word and word in normalized)
        if domain.get("name", "").lower() in normalized:
            score += 2
        if score > best_score:
            best_domain = domain
            best_score = score

    return best_domain


def _detect_intent(question: str) -> str:
    normalized = question.lower()
    if any(word in normalized for word in ("재실", "현재", "있는 사람", "어디")):
        return "occupancy_lookup"
    if any(word in normalized for word in ("출입", "이력", "카드", "in", "out")):
        return "access_history_lookup"
    if any(word in normalized for word in ("교육", "이수", "안전교육")):
        return "education_lookup"
    if any(word in normalized for word in ("점검", "검사", "조치")):
        return "inspection_lookup"
    return "general_table_lookup"



def _mock_answer(
    question: str,
    history: Optional[List[Dict[str, Any]]] = None,
    recent_results: Optional[List[Dict[str, Any]]] = None,
    chat_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context = _build_context(
        question,
        history=history,
        recent_results=recent_results,
        chat_session=chat_session,
    )
    domain = context["domain"]
    intent = context["intent"]
    history_count = int(context.get("history_count") or 0)
    result_count = int(context.get("result_count") or 0)

    lines = [
        "\ud604\uc7ac\ub294 AI \uc870\ud68c \ub3c4\uc6b0\ubbf8 mock \ubaa8\ub4dc\uc785\ub2c8\ub2e4.",
        "",
        f"\uc778\uc2dd\ud55c \ub3c4\uba54\uc778: {domain.get('name', '\ubbf8\ubd84\ub958')}",
        f"\ub300\uc0c1 DB: {domain.get('db') or '\ubbf8\uc9c0\uc815'}",
        f"\uc778\uc2dd\ud55c \uc758\ub3c4: {intent}",
        f"\ucc38\uace0 \ub300\ud654 \uc218: {history_count}\uac74",
        f"\ucc38\uace0 \uacb0\uacfc \uc218: {result_count}\uac74",
        "",
        "\uc544\uc9c1 \uc2e4\uc81c \uc0ac\ub0b4 AI API\ub098 DB \uc870\ud68c\ub294 \uc2e4\ud589\ud558\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4.",
        "\ub2e4\uc74c \ub2e8\uacc4\uc5d0\uc11c \uc0ac\ub0b4 API \uc2a4\ud06c\ub9bd\ud2b8\ub97c \uc5f0\uacb0\ud558\uba74 \uc774 \uc790\ub9ac\uc5d0 \uc2e4\uc81c \ub2f5\ubcc0\uc774 \ud45c\uc2dc\ub429\ub2c8\ub2e4.",
    ]

    return {
        "answer": "\n".join(lines),
        "mode": "mock",
        "intent": intent,
        "domain": domain,
        "history_count": history_count,
        "result_count": result_count,
        "created_at": get_korean_time().isoformat(),
    }


def _real_answer(
    question: str,
    history: Optional[List[Dict[str, Any]]] = None,
    recent_results: Optional[List[Dict[str, Any]]] = None,
    chat_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    section = _get_ai_config()
    module_name = section.get("real_module", "").strip()
    function_name = section.get("real_function", "").strip()
    _prepare_real_module_path(section)
    context = _build_context(
        question,
        history=history,
        recent_results=recent_results,
        chat_session=chat_session,
    )

    if not module_name or not function_name:
        return {
            "answer": "real \ubaa8\ub4dc\uac00 \uc124\uc815\ub418\uc5b4 \uc788\uc9c0\ub9cc real_module/real_function \uac12\uc774 \uc5c6\uc2b5\ub2c8\ub2e4.",
            "mode": "real",
            "intent": "configuration_missing",
            "domain": {},
            "history_count": context.get("history_count", 0),
            "result_count": context.get("result_count", 0),
            "created_at": get_korean_time().isoformat(),
        }

    try:
        module = importlib.import_module(module_name)
        handler = getattr(module, function_name)
        try:
            result = handler(question, context=context)
        except TypeError:
            result = handler(question)
    except Exception as exc:
        logger.exception("AI assistant real handler failed")
        return {
            "answer": f"\uc0ac\ub0b4 AI \ud638\ucd9c \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4: {exc}",
            "mode": "real",
            "intent": "handler_error",
            "domain": {},
            "history_count": context.get("history_count", 0),
            "result_count": context.get("result_count", 0),
            "created_at": get_korean_time().isoformat(),
        }

    if isinstance(result, dict):
        response = {
            "answer": str(result.get("answer", result)),
            "mode": "real",
            "intent": str(result.get("intent", "internal_ai")),
            "domain": result.get("domain", {}),
            "history_count": context.get("history_count", 0),
            "result_count": context.get("result_count", 0),
            "created_at": get_korean_time().isoformat(),
            "raw": result,
        }
        for key in ("structured_result", "structured_results", "result", "results"):
            if key in result:
                response[key] = result[key]
        return response

    return {
        "answer": str(result),
        "mode": "real",
        "intent": "internal_ai",
        "domain": {},
        "history_count": context.get("history_count", 0),
        "created_at": get_korean_time().isoformat(),
    }


def _build_context(
    question: str,
    history: Optional[List[Dict[str, Any]]] = None,
    recent_results: Optional[List[Dict[str, Any]]] = None,
    chat_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    domains = _get_domain_sections()
    domain = _match_domain(question, domains)
    intent = _detect_intent(question)
    safe_history = []
    for item in history or []:
        safe_history.append({
            "role": str(item.get("role") or ""),
            "content": str(item.get("content") or ""),
            "metadata": item.get("metadata") or {},
            "created_at": item.get("created_at") or "",
        })
    return {
        "question": question,
        "domain": domain,
        "intent": intent,
        "history": safe_history,
        "history_count": len(safe_history),
        "recent_results": recent_results or [],
        "result_count": len(recent_results or []),
        "chat_session": chat_session or {},
        "created_at": get_korean_time().isoformat(),
    }

def _sse_event(event: str, payload: Dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _chunk_text(text: str, size: int = 3) -> Iterable[str]:
    for index in range(0, len(text), size):
        yield text[index:index + size]



def _mock_stream_answer(
    question: str,
    delay_ms: int = 25,
    history: Optional[List[Dict[str, Any]]] = None,
    recent_results: Optional[List[Dict[str, Any]]] = None,
    chat_session: Optional[Dict[str, Any]] = None,
) -> Iterable[str]:
    context = _build_context(
        question,
        history=history,
        recent_results=recent_results,
        chat_session=chat_session,
    )
    domain = context["domain"]
    intent = context["intent"]
    history_count = int(context.get("history_count") or 0)
    result_count = int(context.get("result_count") or 0)

    status_steps = [
        "\uc9c8\ubb38 \uc758\ub3c4\ub97c \ubd84\uc11d\ud558\uace0 \uc788\uc2b5\ub2c8\ub2e4.",
        f"\ucd5c\uadfc \ub300\ud654 {history_count}\uac74\uc744 \ud568\uaed8 \ud655\uc778\ud588\uc2b5\ub2c8\ub2e4.",
        f"\ucd5c\uadfc \uc870\ud68c \uacb0\uacfc {result_count}\uac74\uc744 \ud568\uaed8 \ud655\uc778\ud588\uc2b5\ub2c8\ub2e4.",
        f"\uad00\ub828 \ub3c4\uba54\uc778\uc744 \ud655\uc778\ud588\uc2b5\ub2c8\ub2e4: {domain.get('name', '\ubbf8\ubd84\ub958')}",
        "\ub2f5\ubcc0\uc744 \uc815\ub9ac\ud558\uace0 \uc788\uc2b5\ub2c8\ub2e4.",
    ]
    for step in status_steps:
        yield _sse_event("status", {"message": step})
        time.sleep(0.18)

    answer = _mock_answer(
        question,
        history=history,
        recent_results=recent_results,
        chat_session=chat_session,
    ).get("answer", "")
    yield _sse_event("meta", {
        "mode": "mock",
        "intent": intent,
        "domain": domain,
        "history_count": history_count,
        "result_count": result_count,
    })
    for chunk in _chunk_text(answer, 3):
        yield _sse_event("chunk", {"text": chunk})
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)
    yield _sse_event("done", {"message": "\uc644\ub8cc"})

def _coerce_stream_item(item: Any) -> Iterable[str]:
    if item is None:
        return []
    if isinstance(item, bytes):
        text = item.decode("utf-8", errors="replace")
        return [_sse_event("chunk", {"text": text})]
    if isinstance(item, str):
        return [_sse_event("chunk", {"text": item})]
    if isinstance(item, dict):
        event = str(item.get("event") or item.get("type") or "chunk")
        if event == "chunk" and "text" not in item:
            item = {"text": str(item.get("chunk") or item.get("answer") or item)}
        return [_sse_event(event, item)]
    return [_sse_event("chunk", {"text": str(item)})]



def _real_stream_answer(
    question: str,
    history: Optional[List[Dict[str, Any]]] = None,
    recent_results: Optional[List[Dict[str, Any]]] = None,
    chat_session: Optional[Dict[str, Any]] = None,
) -> Iterable[str]:
    section = _get_ai_config()
    module_name = section.get("real_module", "").strip()
    function_name = (
        section.get("real_stream_function", "").strip()
        or section.get("real_function", "").strip()
    )
    _prepare_real_module_path(section)

    if not module_name or not function_name:
        yield _sse_event("error", {
            "message": "real \ubaa8\ub4dc\uac00 \uc124\uc815\ub418\uc5b4 \uc788\uc9c0\ub9cc real_module/real_stream_function \uac12\uc774 \uc5c6\uc2b5\ub2c8\ub2e4."
        })
        return

    context = _build_context(
        question,
        history=history,
        recent_results=recent_results,
        chat_session=chat_session,
    )
    yield _sse_event("status", {"message": "\uc0ac\ub0b4 AI \ubaa8\ub4c8\uc744 \ud638\ucd9c\ud558\uace0 \uc788\uc2b5\ub2c8\ub2e4."})

    try:
        module = importlib.import_module(module_name)
        handler = getattr(module, function_name)
        try:
            result = handler(question, context=context)
        except TypeError:
            result = handler(question)

        if isinstance(result, dict):
            answer = str(result.get("answer", result))
            meta = {
                "mode": "real",
                "intent": result.get("intent", context["intent"]),
                "domain": result.get("domain", context["domain"]),
                "history_count": context.get("history_count", 0),
                "result_count": context.get("result_count", 0),
            }
            for key in ("structured_result", "structured_results", "result", "results"):
                if key in result:
                    meta[key] = result[key]
            yield _sse_event("meta", meta)
            for chunk in _chunk_text(answer, 3):
                yield _sse_event("chunk", {"text": chunk})
            yield _sse_event("done", {"message": "\uc644\ub8cc"})
            return

        if isinstance(result, str):
            yield _sse_event("meta", {
                "mode": "real",
                "intent": context["intent"],
                "domain": context["domain"],
                "history_count": context.get("history_count", 0),
                "result_count": context.get("result_count", 0),
            })
            for chunk in _chunk_text(result, 3):
                yield _sse_event("chunk", {"text": chunk})
            yield _sse_event("done", {"message": "\uc644\ub8cc"})
            return

        for item in result:
            for event_text in _coerce_stream_item(item):
                yield event_text
        yield _sse_event("done", {"message": "\uc644\ub8cc"})
    except Exception as exc:
        logger.exception("AI assistant real stream handler failed")
        yield _sse_event("error", {"message": f"\uc0ac\ub0b4 AI \uc2a4\ud2b8\ub9ac\ubc0d \ud638\ucd9c \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4: {exc}"})

def _prepare_real_module_path(section: configparser.SectionProxy) -> None:
    raw_paths = section.get("real_module_path", "").strip()
    if not raw_paths:
        return

    for raw_path in raw_paths.split(";"):
        raw_path = raw_path.strip().strip('"')
        if not raw_path:
            continue

        module_path = Path(raw_path).expanduser()
        import_dir = module_path.parent if module_path.suffix.lower() == ".py" else module_path
        import_dir_text = str(import_dir)

        if import_dir_text and import_dir_text not in sys.path:
            sys.path.insert(0, import_dir_text)


@ai_assistant_bp.route("/api/ai-assistant/sessions", methods=["GET"])
def ai_assistant_sessions():
    permission_response = enforce_permission(AI_ASSISTANT_MENU_CODE, "view", response_type="json")
    if permission_response:
        return permission_response

    login_id = _current_login_id()
    if not login_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    conn = None
    try:
        conn = get_db_connection()
        _ensure_chat_tables(conn)
        conn.commit()
        rows = conn.execute(
            """
            SELECT id, title, created_at, updated_at
              FROM ai_chat_sessions
             WHERE created_by_login = %s
               AND COALESCE(is_deleted, FALSE) = FALSE
             ORDER BY updated_at DESC, id DESC
             LIMIT 100
            """,
            (login_id,),
        ).fetchall()
        return jsonify({"success": True, "sessions": [_serialize_chat_session(row) for row in rows]})
    except Exception as exc:
        logger.exception("AI chat session list failed")
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        if conn:
            conn.close()


@ai_assistant_bp.route("/api/ai-assistant/sessions", methods=["POST"])
def ai_assistant_create_session():
    permission_response = enforce_permission(AI_ASSISTANT_MENU_CODE, "view", response_type="json")
    if permission_response:
        return permission_response

    login_id = _current_login_id()
    if not login_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "새 대화").strip() or "새 대화"

    conn = None
    try:
        conn = get_db_connection()
        _ensure_chat_tables(conn)
        chat_session = _create_chat_session(conn, login_id, title[:80])
        conn.commit()
        return jsonify({"success": True, "session": chat_session})
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.exception("AI chat session create failed")
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        if conn:
            conn.close()


@ai_assistant_bp.route("/api/ai-assistant/sessions/<int:chat_session_id>/messages", methods=["GET"])
def ai_assistant_session_messages(chat_session_id: int):
    permission_response = enforce_permission(AI_ASSISTANT_MENU_CODE, "view", response_type="json")
    if permission_response:
        return permission_response

    login_id = _current_login_id()
    if not login_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    conn = None
    try:
        conn = get_db_connection()
        _ensure_chat_tables(conn)
        conn.commit()
        chat_session = _get_owned_chat_session(conn, chat_session_id, login_id)
        if not chat_session:
            return jsonify({"success": False, "message": "대화방을 찾을 수 없습니다."}), 404
        rows = conn.execute(
            """
            SELECT id, session_id, role, content, metadata, created_at
              FROM ai_chat_messages
             WHERE session_id = %s
             ORDER BY created_at ASC, id ASC
            """,
            (chat_session_id,),
        ).fetchall()
        return jsonify({
            "success": True,
            "session": chat_session,
            "messages": [_serialize_chat_message(row) for row in rows],
        })
    except Exception as exc:
        logger.exception("AI chat messages lookup failed")
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        if conn:
            conn.close()


@ai_assistant_bp.route("/api/ai-assistant/sessions/<int:chat_session_id>", methods=["DELETE"])
def ai_assistant_delete_session(chat_session_id: int):
    permission_response = enforce_permission(AI_ASSISTANT_MENU_CODE, "view", response_type="json")
    if permission_response:
        return permission_response

    login_id = _current_login_id()
    if not login_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    conn = None
    try:
        conn = get_db_connection()
        _ensure_chat_tables(conn)
        result = conn.execute(
            """
            UPDATE ai_chat_sessions
               SET is_deleted = TRUE,
                   updated_at = CURRENT_TIMESTAMP
             WHERE id = %s
               AND created_by_login = %s
               AND COALESCE(is_deleted, FALSE) = FALSE
            """,
            (chat_session_id, login_id),
        )
        conn.commit()
        deleted_count = getattr(result, "rowcount", 0)
        if deleted_count == 0:
            return jsonify({"success": False, "message": "대화방을 찾을 수 없습니다."}), 404
        return jsonify({"success": True})
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.exception("AI chat session delete failed")
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        if conn:
            conn.close()


@ai_assistant_bp.route("/ai-assistant")
def ai_assistant_page():
    permission_response = enforce_permission(AI_ASSISTANT_MENU_CODE, "view")
    if permission_response:
        return permission_response

    section = _get_ai_config()
    domains = _get_domain_sections()
    return render_template(
        "ai-assistant.html",
        menu=MENU_CONFIG,
        ai_mode=section.get("mode", DEFAULT_MODE),
        ai_enabled=section.getboolean("enabled", fallback=True),
        domains=domains,
    )


@ai_assistant_bp.route("/api/ai-assistant/chat", methods=["POST"])
def ai_assistant_chat():
    permission_response = enforce_permission(AI_ASSISTANT_MENU_CODE, "view", response_type="json")
    if permission_response:
        return permission_response

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"success": False, "message": "질문을 입력해 주세요."}), 400
    if len(question) > 2000:
        return jsonify({"success": False, "message": "질문은 2,000자 이하로 입력해 주세요."}), 400

    section = _get_ai_config()
    enabled = section.getboolean("enabled", fallback=True)
    mode = section.get("mode", DEFAULT_MODE).strip().lower() or DEFAULT_MODE

    if not enabled:
        return jsonify({"success": False, "message": "AI 조회 도우미가 비활성화되어 있습니다."}), 403

    login_id = _current_login_id()
    if not login_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    chat_session = None
    chat_history: List[Dict[str, Any]] = []
    recent_results: List[Dict[str, Any]] = []
    conn = None
    try:
        conn = get_db_connection()
        _ensure_chat_tables(conn)
        chat_session, _created = _get_or_create_chat_session(
            conn,
            login_id,
            payload.get("session_id"),
            question,
        )
        if not _created:
            chat_history = _load_recent_chat_history(conn, int(chat_session["id"]))
            recent_results = _load_recent_chat_results(conn, int(chat_session["id"]))
        _save_chat_message(conn, int(chat_session["id"]), "user", question)
        conn.commit()
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 404
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.exception("AI chat message pre-save failed")
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        if conn:
            conn.close()

    if mode == "real":
        result = _real_answer(
            question,
            history=chat_history,
            recent_results=recent_results,
            chat_session=chat_session,
        )
    else:
        result = _mock_answer(
            question,
            history=chat_history,
            recent_results=recent_results,
            chat_session=chat_session,
        )

    conn = None
    try:
        conn = get_db_connection()
        _ensure_chat_tables(conn)
        assistant_message_id = _save_chat_message(
            conn,
            int(chat_session["id"]),
            "assistant",
            str(result.get("answer") or ""),
            {
                "mode": result.get("mode"),
                "intent": result.get("intent"),
                "domain": result.get("domain", {}),
                "history_count": result.get("history_count", len(chat_history)),
                "result_count": result.get("result_count", len(recent_results)),
            },
        )
        _save_chat_results(conn, int(chat_session["id"]), assistant_message_id, result)
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        logger.debug("AI chat assistant message save skipped", exc_info=True)
    finally:
        if conn:
            conn.close()

    return jsonify({"success": True, "data": result, "session": chat_session})


@ai_assistant_bp.route("/api/ai-assistant/chat-stream", methods=["POST"])
def ai_assistant_chat_stream():
    permission_response = enforce_permission(AI_ASSISTANT_MENU_CODE, "view", response_type="json")
    if permission_response:
        return permission_response

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"success": False, "message": "질문을 입력해 주세요."}), 400
    if len(question) > 2000:
        return jsonify({"success": False, "message": "질문은 2,000자 이하로 입력해 주세요."}), 400

    section = _get_ai_config()
    enabled = section.getboolean("enabled", fallback=True)
    mode = section.get("mode", DEFAULT_MODE).strip().lower() or DEFAULT_MODE
    delay_ms = section.getint("mock_stream_delay_ms", fallback=25)

    if not enabled:
        return jsonify({"success": False, "message": "AI 조회 도우미가 비활성화되어 있습니다."}), 403

    login_id = _current_login_id()
    if not login_id:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    chat_history: List[Dict[str, Any]] = []
    recent_results: List[Dict[str, Any]] = []
    conn = None
    try:
        conn = get_db_connection()
        _ensure_chat_tables(conn)
        chat_session, _created = _get_or_create_chat_session(
            conn,
            login_id,
            payload.get("session_id"),
            question,
        )
        if not _created:
            chat_history = _load_recent_chat_history(conn, int(chat_session["id"]))
            recent_results = _load_recent_chat_results(conn, int(chat_session["id"]))
        _save_chat_message(conn, int(chat_session["id"]), "user", question)
        conn.commit()
    except PermissionError as exc:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(exc)}), 404
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.exception("AI stream session prepare failed")
        return jsonify({"success": False, "message": str(exc)}), 500
    finally:
        if conn:
            conn.close()

    def generate():
        assistant_chunks: List[str] = []
        assistant_meta: Dict[str, Any] = {}
        assistant_results: List[Dict[str, Any]] = []
        yield _sse_event("session", chat_session)
        yield _sse_event("status", {"message": "요청을 접수했습니다."})
        source = (
            _real_stream_answer(
                question,
                history=chat_history,
                recent_results=recent_results,
                chat_session=chat_session,
            )
            if mode in {"real", "internal"}
            else _mock_stream_answer(
                question,
                delay_ms=delay_ms,
                history=chat_history,
                recent_results=recent_results,
                chat_session=chat_session,
            )
        )
        for event_text in source:
            event_name, event_payload = _decode_sse_event_text(event_text)
            if event_name == "chunk":
                assistant_chunks.append(str(event_payload.get("text") or ""))
            elif event_name == "meta":
                assistant_meta = event_payload
            elif event_name in {"result", "structured_result"}:
                assistant_results.append(event_payload)
            elif event_name in {"results", "structured_results"}:
                payload_results = event_payload.get("results") or event_payload.get("structured_results")
                if isinstance(payload_results, list):
                    assistant_results.extend(item for item in payload_results if isinstance(item, dict))
            yield event_text

        assistant_text = "".join(assistant_chunks)
        if assistant_text.strip():
            save_conn = None
            try:
                save_conn = get_db_connection()
                _ensure_chat_tables(save_conn)
                assistant_message_id = _save_chat_message(
                    save_conn,
                    int(chat_session["id"]),
                    "assistant",
                    assistant_text,
                    assistant_meta,
                )
                result_payload = dict(assistant_meta)
                if assistant_results:
                    result_payload["structured_results"] = assistant_results
                _save_chat_results(save_conn, int(chat_session["id"]), assistant_message_id, result_payload)
                save_conn.commit()
            except Exception:
                if save_conn:
                    save_conn.rollback()
                logger.debug("AI stream assistant message save skipped", exc_info=True)
            finally:
                if save_conn:
                    save_conn.close()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
