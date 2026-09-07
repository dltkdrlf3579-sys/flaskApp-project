import hashlib
import json
import math
import re
import threading
import time
from collections import defaultdict
from pathlib import Path

from .settings import bounded_int, configured_path


ALLOWED_FILES = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".hwp", ".hwpx", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".webp"}
IMAGE_FILES = {".png", ".jpg", ".jpeg", ".webp"}
_CACHE = {}
_LOCK = threading.Lock()


class KnowledgeError(RuntimeError):
    pass


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contained_path(root, relative):
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise KnowledgeError("자료 경로가 지정된 폴더 밖을 가리킵니다. 이관 매뉴얼의 자료 묶음 만들기를 이용하세요.") from exc
    return path


def source_key(domain, source):
    return hashlib.sha256((domain + "/" + source).encode("utf-8")).hexdigest()[:24]


def words(text):
    return set(re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE))


class KnowledgeStore:
    def __init__(self, config):
        self.root = configured_path(config, "AI_KNOWLEDGE", "root_folder")
        self.index_path = contained_path(self.root, config.get("AI_KNOWLEDGE", "index_file", fallback="cache/knowledge_index.jsonl"))
        self.domains = tuple(part.strip() for part in config.get("AI_KNOWLEDGE", "domains", fallback="safety_training,safety_law").split(",") if part.strip())
        self.sources = {}
        self.chunks = []
        self.postings = defaultdict(set)
        self.page_artifacts = defaultdict(set)
        self.page_chunks = defaultdict(list)
        self.validation_cache = {}
        self.validation_lock = threading.Lock()
        self.dependencies = []
        self.loaded_signature = []
        self._load_sources()
        self._load_index()
        self._load_downloads()
        self._resolve_originals()
        self.assert_unchanged()

    def _watch(self, path):
        self.dependencies.append(path)
        self.loaded_signature.append((str(path), path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else (str(path), 0, 0))

    def assert_unchanged(self):
        if self.signature() != tuple(self.loaded_signature):
            raise KnowledgeError("검색 자료가 갱신 중입니다. 자료 갱신이 끝난 후 다시 시도하세요.")

    def _load_sources(self):
        for domain in self.domains:
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", domain):
                raise KnowledgeError("자료 도메인 설정이 올바르지 않습니다.")
            registry_path = contained_path(self.root, "knowledge/{}/source_registry.json".format(domain))
            self._watch(registry_path)
            if not registry_path.is_file():
                raise KnowledgeError("자료 등록 목록이 없습니다: knowledge/{}/source_registry.json".format(domain))
            registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
            for record in registry.get("sources", []):
                name = str(record.get("source") or "")
                expected = str(record.get("file_sha256") or "")
                if record.get("status") != "active":
                    continue
                if Path(name).name != name or "/" in name or "\\" in name or Path(name).suffix.lower() not in ALLOWED_FILES:
                    raise KnowledgeError("자료 등록 목록에 허용되지 않는 파일 경로가 있습니다.")
                if not re.fullmatch(r"[a-f0-9]{64}", expected):
                    raise KnowledgeError("등록 자료의 원본 해시가 없습니다: " + name)
                identifier = source_key(domain, name)
                self.sources[identifier] = {
                    "id": identifier, "domain": domain, "name": name,
                    "relative_path": "knowledge/{}/docs/{}".format(domain, name),
                    "sha256": expected, "record": record, "downloads": [],
                }

    def _load_index(self):
        if not self.index_path.is_file():
            raise KnowledgeError("기존 검색 색인이 없습니다. cache/knowledge_index.jsonl을 함께 옮겨 주세요.")
        self._watch(self.index_path)
        with self.index_path.open(encoding="utf-8-sig") as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                identifier = source_key(str(row.get("domain") or ""), str(row.get("source") or ""))
                if identifier not in self.sources or row.get("source_status") != "active":
                    continue
                if row.get("registry_hash_status") != "verified":
                    continue
                if row.get("quality_status") in {"failed", "rejected", "excluded", "unresolved"}:
                    continue
                text = str(row.get("text") or "").strip()
                if not text:
                    continue
                page = row.get("page")
                page = page if isinstance(page, int) and not isinstance(page, bool) and page > 0 else None
                entry = {"source_id": identifier, "page": page, "text": text, "index_id": str(row.get("id") or "")}
                number = len(self.chunks)
                self.chunks.append(entry)
                if page:
                    self.page_chunks[(identifier, page)].append(number)
                tokens = {str(token).casefold() for token in row.get("tokens", [])} | words(self.sources[identifier]["name"])
                for token in tokens:
                    self.postings[token].add(number)
                artifact = str(row.get("page_artifact_id") or "")
                if page and re.fullmatch(r"[a-f0-9]{64}", artifact):
                    self.page_artifacts[(identifier, page)].add(artifact)
        if not self.chunks:
            raise KnowledgeError("선택한 도메인에 검증된 검색 자료가 없습니다.")

    def _load_downloads(self):
        catalog_path = contained_path(self.root, "public_downloads/_catalog.json")
        self._watch(catalog_path)
        if not catalog_path.is_file():
            return
        catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
        for relative, metadata in catalog.get("files", {}).items():
            if metadata.get("enabled", True) is False or Path(relative).suffix.lower() not in ALLOWED_FILES:
                continue
            normalized = relative.replace("\\", "/")
            if Path(normalized).is_absolute() or ".." in Path(normalized).parts:
                raise KnowledgeError("다운로드 목록의 경로가 올바르지 않습니다.")
            for source in self.sources.values():
                record = source["record"]
                linked = normalized in record.get("related_public_downloads", [])
                linked = linked or source["name"] in metadata.get("related_knowledge_sources", [])
                linked = linked or bool(record.get("logical_resource_id") and record["logical_resource_id"] == metadata.get("logical_resource_id"))
                if linked:
                    path = "public_downloads/" + normalized
                    file_id = hashlib.sha256(path.encode("utf-8")).hexdigest()[:24]
                    source["downloads"].append({"id": file_id, "relative_path": path, "name": Path(normalized).name})

    def _resolve_originals(self):
        for source in self.sources.values():
            if (self.root / source["relative_path"]).is_file():
                continue
            for item in source["downloads"]:
                candidate = self.root / item["relative_path"]
                if candidate.is_file() and digest_file(candidate) == source["sha256"]:
                    source["relative_path"] = item["relative_path"]
                    break

    def signature(self):
        return tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else (str(path), 0, 0) for path in self.dependencies)

    def catalog(self):
        active = {chunk["source_id"] for chunk in self.chunks}
        return [{"id": source["id"], "title": source["name"], "domain": source["domain"]} for source in self.sources.values() if source["id"] in active]

    def verified_source(self, identifier):
        source = self.sources.get(identifier)
        if source is None:
            raise KnowledgeError("등록되지 않은 자료입니다.")
        path = contained_path(self.root, source["relative_path"])
        if not path.is_file():
            raise KnowledgeError("원본 파일이 없습니다: " + source["name"])
        signature = (path.stat().st_mtime_ns, path.stat().st_size, source["sha256"])
        with self.validation_lock:
            if self.validation_cache.get(identifier) != signature:
                if digest_file(path) != source["sha256"]:
                    raise KnowledgeError("원본과 검색 자료의 버전이 다릅니다. 검증된 자료 묶음으로 갱신해 주세요: " + source["name"])
                self.validation_cache[identifier] = signature
        return source, path

    def search(self, terms, source_ids=None, pages=None, limit=8):
        chosen_sources = set(source_ids or [])
        chosen_pages = set(pages or [])
        scores = defaultdict(float)
        query_tokens = set().union(*(words(term) for term in terms)) if terms else set()
        for token in query_tokens:
            matching = set(self.postings.get(token, set()))
            if len(token) >= 2:
                for indexed, postings in self.postings.items():
                    if indexed.startswith(token):
                        matching.update(postings)
            weight = math.log(1 + len(self.chunks) / (1 + len(matching)))
            for number in matching:
                scores[number] += weight
        if chosen_sources:
            for number, chunk in enumerate(self.chunks):
                if chunk["source_id"] in chosen_sources and (not chosen_pages or chunk["page"] in chosen_pages):
                    scores[number] += 0.1
        candidates = []
        for number, score in scores.items():
            chunk = self.chunks[number]
            if chosen_sources and chunk["source_id"] not in chosen_sources:
                continue
            if chosen_pages and chunk["page"] not in chosen_pages:
                continue
            title = self.sources[chunk["source_id"]]["name"].casefold()
            title_score = sum(2 for token in query_tokens if len(token) >= 2 and token in title)
            candidates.append((score + title_score, number))
        selected = []
        seen = set()
        for score, number in sorted(candidates, reverse=True):
            entry = self.chunks[number]
            identity = (entry["source_id"], entry["page"] if entry["page"] else entry["index_id"])
            if identity in seen:
                continue
            self.verified_source(entry["source_id"])
            seen.add(identity)
            result = dict(entry)
            siblings = self.page_chunks.get((entry["source_id"], entry["page"]), [])
            if len(siblings) > 1:
                context = []
                budget = 10000
                for neighbor in sorted(siblings, key=lambda other: abs(other - number))[:5]:
                    excerpt = self.chunks[neighbor]["text"][:budget]
                    if excerpt and excerpt not in context:
                        context.append(excerpt)
                        budget -= len(excerpt)
                    if budget <= 0:
                        break
                result["text"] = "\n\n".join(context)
            selected.append(result)
            if len(selected) >= limit:
                break
        return selected

    def artifact_image(self, identifier, page):
        self.verified_source(identifier)
        artifact_root = contained_path(self.root, "artifacts/document_understanding")
        for artifact_id in sorted(self.page_artifacts.get((identifier, page), set())):
            metadata_path = contained_path(artifact_root, "pages/" + artifact_id + ".json")
            if not metadata_path.is_file():
                continue
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
            if metadata.get("artifact_id") != artifact_id:
                continue
            relative = str(metadata.get("page_image_path") or "")
            if not relative.startswith("images/pages/"):
                continue
            path = contained_path(artifact_root, relative)
            if path.is_file() and path.suffix.lower() in IMAGE_FILES:
                return path
        return None

    def file_resource(self, identifier, download_id=None):
        source, original = self.verified_source(identifier)
        if download_id is None:
            return original
        for item in source["downloads"]:
            if item["id"] == download_id:
                path = contained_path(self.root, item["relative_path"])
                if path.is_file():
                    return path
        raise KnowledgeError("요청한 첨부자료가 없거나 연결이 해제되었습니다.")


def get_store(config):
    root = configured_path(config, "AI_KNOWLEDGE", "root_folder")
    key = (str(root), config.get("AI_KNOWLEDGE", "domains", fallback="safety_training,safety_law"),
           config.get("AI_KNOWLEDGE", "index_file", fallback="cache/knowledge_index.jsonl"))
    refresh = bounded_int(config, "AI_KNOWLEDGE", "reload_seconds", 180, 1, 86400)
    with _LOCK:
        cached = _CACHE.get("current")
        now = time.monotonic()
        if cached and cached[0] == key:
            store, signature, checked = cached[1:]
            if now - checked < refresh:
                return store
            if signature == store.signature():
                _CACHE["current"] = (key, store, signature, now)
                return store
        store = KnowledgeStore(config)
        _CACHE["current"] = (key, store, store.signature(), now)
        return store
