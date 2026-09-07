import json
import time
import uuid
from urllib.parse import urlsplit

import requests

from .settings import configured_path


class InternalApiError(RuntimeError):
    pass


class InternalChatClient:
    def __init__(self, config, model_name=None):
        self.config = config
        section = "AI_INTERNAL_API"
        required = ("base_url", "x_dep_ticket", "send_system_name", "user_id", "user_type")
        if model_name is None:
            required += ("model_name",)
        missing = [key for key in required if not config.get(section, key, fallback="").strip()]
        if missing:
            raise InternalApiError("[AI_INTERNAL_API] 설정을 입력해 주세요: " + ", ".join(missing))
        base = config.get(section, "base_url").strip().rstrip("/")
        suffix = config.get(section, "chat_path", fallback="chat/completions").strip().strip("/")
        self.url = base + ("/" + suffix if suffix else "")
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise InternalApiError("base_url에는 인증정보 없는 http/https API 주소를 입력하세요.")
        self.model = (config.get(section, "model_name") if model_name is None else model_name).strip()
        if not self.model:
            raise InternalApiError("사내 AI 모델명이 비어 있습니다.")
        self.timeout = (
            config.getfloat(section, "connect_timeout_seconds", fallback=10),
            config.getfloat(section, "timeout_seconds", fallback=180),
        )
        if any(value <= 0 for value in self.timeout):
            raise InternalApiError("API 대기시간은 0보다 커야 합니다.")
        self.deadline_seconds = config.getfloat(section, "total_timeout_seconds", fallback=240)
        if self.deadline_seconds <= 0:
            raise InternalApiError("total_timeout_seconds는 0보다 커야 합니다.")
        self.verify = config.getboolean(section, "verify_ssl", fallback=True)
        if config.get(section, "ca_bundle", fallback="").strip():
            self.verify = str(configured_path(config, section, "ca_bundle"))
        self.proxy = config.get(section, "proxy_url", fallback="").strip()
        self.streaming = config.getboolean(section, "streaming", fallback=True)

    def headers(self):
        section = "AI_INTERNAL_API"
        result = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.config.get(section, "api_key", fallback="api_key").strip(),
        }
        for header, key in (("x-dep-ticket", "x_dep_ticket"), ("Send-System-Name", "send_system_name"),
                            ("User-Id", "user_id"), ("User-Type", "user_type")):
            result[header] = self.config.get(section, key).strip()
        for header, key in (("Prompt-Msg-Id", "prompt_msg_id"), ("Completion-Msg-Id", "completion_msg_id")):
            value = self.config.get(section, key, fallback="auto").strip()
            result[header] = str(uuid.uuid4()) if value.lower() in {"", "auto", "uuid", "uuid4"} else value
        return result

    def complete(self, messages):
        return "".join(self.generate(messages, stream=False))

    def generate(self, messages, stream=True):
        streaming = stream and self.streaming
        payload = {
            "model": self.model, "messages": messages, "stream": streaming,
            "temperature": self.config.getfloat("AI_INTERNAL_API", "temperature", fallback=0.0),
        }
        max_tokens = self.config.getint("AI_INTERNAL_API", "max_tokens", fallback=0)
        if max_tokens > 0:
            payload["max_tokens"] = max_tokens
        started = time.monotonic()
        try:
            with requests.Session() as connection:
                connection.trust_env = False
                if self.proxy:
                    connection.proxies = {"http": self.proxy, "https": self.proxy}
                with connection.post(self.url, json=payload, headers=self.headers(), stream=True,
                                     timeout=self.timeout, verify=self.verify, allow_redirects=False) as response:
                    if response.status_code != 200:
                        raise InternalApiError("사내 AI 호출 실패(HTTP {}). API 주소·인증값·모델·호출 제한을 확인하세요.".format(response.status_code))
                    response.encoding = "utf-8"
                    if not streaming:
                        body = bytearray()
                        for chunk in response.iter_content(chunk_size=4096):
                            self._check_deadline(started)
                            body.extend(chunk)
                            if len(body) > 2_000_000:
                                raise InternalApiError("사내 AI 응답이 허용 크기를 초과했습니다.")
                        data = json.loads(body.decode("utf-8"))
                        yield self._content(data, False)
                        return
                    if "text/event-stream" not in response.headers.get("Content-Type", "").lower():
                        raise InternalApiError("스트리밍 응답 형식이 아닙니다. API가 미지원이면 streaming = false로 설정하세요.")
                    data_lines = []
                    completed = False
                    size = 0
                    for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                        self._check_deadline(started)
                        size += len(line)
                        if size > 2_000_000:
                            raise InternalApiError("사내 AI 스트리밍 응답이 허용 크기를 초과했습니다.")
                        if line.startswith("data:"):
                            data_lines.append(line[5:].lstrip())
                        elif not line and data_lines:
                            data = "\n".join(data_lines)
                            data_lines = []
                            if data == "[DONE]":
                                completed = True
                                break
                            event = json.loads(data)
                            text = self._content(event, True)
                            if text:
                                yield text
                            for choice in event.get("choices", []):
                                reason = choice.get("finish_reason")
                                if reason in {"length", "content_filter"}:
                                    raise InternalApiError("AI 답변이 중단되었습니다({}).".format(reason))
                                if reason == "stop":
                                    completed = True
                    if not completed:
                        raise InternalApiError("사내 AI 연결이 답변 완료 전에 종료되었습니다.")
        except requests.Timeout as exc:
            raise InternalApiError("사내 AI 응답 대기시간을 초과했습니다.") from exc
        except requests.RequestException as exc:
            raise InternalApiError("사내 AI 서버에 연결하지 못했습니다. 사내망·주소·인증서·프록시를 확인하세요.") from exc
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise InternalApiError("사내 AI 응답 형식이 Chat Completions 규약과 다릅니다.") from exc

    def _check_deadline(self, started):
        if time.monotonic() - started > self.deadline_seconds:
            raise InternalApiError("사내 AI 호출의 전체 제한시간을 초과했습니다.")

    @staticmethod
    def _content(data, streaming):
        if data.get("error"):
            raise InternalApiError("사내 AI 서버가 오류를 반환했습니다.")
        choices = data.get("choices", [])
        if not choices:
            if streaming:
                return ""
            raise InternalApiError("사내 AI 응답에 답변이 없습니다.")
        choice = choices[0]
        if choice.get("finish_reason") in {"length", "content_filter"}:
            raise InternalApiError("AI 답변이 완성되지 않았습니다.")
        content = choice.get("delta" if streaming else "message", {}).get("content")
        if content is None and streaming:
            return ""
        if not isinstance(content, str):
            raise InternalApiError("사내 AI가 텍스트 답변을 반환하지 않았습니다.")
        return content
