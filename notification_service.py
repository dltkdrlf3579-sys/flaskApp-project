"""Simplified notification service for event-based chatbot alerts."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from database_config import db_config
from db_connection import get_db_connection

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Raised when notification delivery fails."""


class BaseChannelAdapter:
    def send(self, payload: Dict[str, Any]) -> Tuple[int, str]:
        raise NotImplementedError


class ChatbotChannelAdapter(BaseChannelAdapter):
    """Webhook 기반 챗봇 채널 어댑터."""

    def __init__(self, config_section) -> None:
        get_value = config_section.get if hasattr(config_section, 'get') else (lambda key, default=None: default)
        self.webhook_url = get_value('chatbot_webhook_url')
        self.auth_token = get_value('chatbot_auth_token')
        if hasattr(config_section, 'getint'):
            self.timeout = config_section.getint('chatbot_timeout', fallback=5)
        else:
            try:
                self.timeout = int(get_value('chatbot_timeout', 5))
            except Exception:
                self.timeout = 5

    def send(self, payload: Dict[str, Any]) -> Tuple[int, str]:
        if not self.webhook_url:
            raise NotificationError("chatbot_webhook_url 설정이 필요합니다.")

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        try:
            response = requests.post(
                self.webhook_url,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False),
                timeout=self.timeout,
            )
            return response.status_code, response.text
        except requests.RequestException as exc:
            raise NotificationError(f"챗봇 전송 실패: {exc}") from exc


class NotificationService:
    """이벤트 기반 알림을 채널로 전송하는 간단한 서비스."""

    _instance: Optional["NotificationService"] = None

    def __init__(self) -> None:
        self.config = db_config.config
        self.channel_adapters: Dict[str, BaseChannelAdapter] = {}
        self._prepare_adapters()
        self._ensure_log_table()

    @classmethod
    def instance(cls) -> "NotificationService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    def _prepare_adapters(self) -> None:
        section = self.config["NOTIFICATION"] if self.config.has_section("NOTIFICATION") else {}
        self.channel_adapters['chatbot'] = ChatbotChannelAdapter(section)

    def _ensure_log_table(self) -> None:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notification_logs (
                        id SERIAL PRIMARY KEY,
                        channel VARCHAR(50) NOT NULL,
                        recipient_type VARCHAR(50),
                        recipient_id VARCHAR(255),
                        template_key VARCHAR(100),
                        payload TEXT,
                        status VARCHAR(20),
                        response_code INTEGER,
                        response_body TEXT,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            else:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notification_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel TEXT NOT NULL,
                        recipient_type TEXT,
                        recipient_id TEXT,
                        template_key TEXT,
                        payload TEXT,
                        status TEXT,
                        response_code INTEGER,
                        response_body TEXT,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    # ------------------------------------------------------------------
    def send_event_notification(
        self,
        *,
        channel: str,
        event: str,
        recipients: Iterable[str],
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        adapter = self.channel_adapters.get(channel)
        if not adapter:
            raise NotificationError(f"지원하지 않는 채널입니다: {channel}")

        recipient_list: List[str] = [str(r).strip() for r in recipients if str(r).strip()]
        if not recipient_list:
            raise NotificationError("recipients 목록이 비어 있습니다.")
        if not event:
            raise NotificationError("event 값은 필수입니다.")

        payload: Dict[str, Any] = {
            'event': event,
            'recipients': recipient_list,
            'context': context or {},
        }
        if metadata:
            payload['metadata'] = metadata

        status = 'sent'
        response_code: Optional[int] = None
        response_body: Optional[str] = None
        error_message: Optional[str] = None

        try:
            response_code, response_body = adapter.send(payload)
            if response_code >= 400:
                status = 'failed'
                error_message = f"채널 응답 코드 {response_code}"
                raise NotificationError(error_message)
        except NotificationError as exc:
            status = 'error' if status == 'sent' else status
            error_message = str(exc)
            self._log_event(channel, recipient_list, event, payload, status, response_code, response_body, error_message)
            logger.warning("Notification delivery failed: %s", exc)
            raise
        except Exception as exc:
            status = 'error'
            error_message = str(exc)
            self._log_event(channel, recipient_list, event, payload, status, response_code, response_body, error_message)
            logger.exception("Notification unexpected error")
            raise NotificationError("알림 전송 중 예기치 않은 오류가 발생했습니다.") from exc

        self._log_event(channel, recipient_list, event, payload, status, response_code, response_body, error_message)
        return {
            'success': True,
            'status': status,
            'response_code': response_code,
        }

    # ------------------------------------------------------------------
    def _log_event(
        self,
        channel: str,
        recipients: List[str],
        event: str,
        payload: Dict[str, Any],
        status: str,
        response_code: Optional[int],
        response_body: Optional[str],
        error_message: Optional[str],
    ) -> None:
        conn = get_db_connection()
        cursor = conn.cursor()
        recipient_type = 'list' if len(recipients) > 1 else 'user'
        recipient_id = ','.join(recipients)
        payload_json = json.dumps(payload, ensure_ascii=False)

        try:
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                cursor.execute(
                    """
                    INSERT INTO notification_logs (
                        channel, recipient_type, recipient_id,
                        template_key, payload, status,
                        response_code, response_body, error_message
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        channel,
                        recipient_type,
                        recipient_id,
                        event,
                        payload_json,
                        status,
                        response_code,
                        response_body,
                        error_message,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO notification_logs (
                        channel, recipient_type, recipient_id,
                        template_key, payload, status,
                        response_code, response_body, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        channel,
                        recipient_type,
                        recipient_id,
                        event,
                        payload_json,
                        status,
                        response_code,
                        response_body,
                        error_message,
                    ),
                )
            conn.commit()
        except Exception:
            logger.exception("Failed to log notification event")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()


# 편의 함수
def get_notification_service() -> NotificationService:
    return NotificationService.instance()
