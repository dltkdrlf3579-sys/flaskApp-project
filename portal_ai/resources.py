import hashlib
import threading

from .knowledge import KnowledgeError, get_store, IMAGE_FILES
from .settings import configured_path


_RENDER_LOCK = threading.Lock()


def preview_path(config, identifier, page):
    store = get_store(config)
    source, original = store.verified_source(identifier)
    if not 1 <= page <= 10000 or not any(hit["source_id"] == identifier and hit["page"] == page for hit in store.chunks):
        raise KnowledgeError("등록된 검색 페이지가 아닙니다.")
    artifact = store.artifact_image(identifier, page)
    if artifact:
        return artifact
    if original.suffix.lower() != ".pdf":
        raise KnowledgeError("이 자료의 페이지 이미지가 준비되지 않았습니다. 원본 파일을 확인하세요.")
    try:
        import pymupdf
    except ImportError as exc:
        raise KnowledgeError("PDF 미리보기를 위해 requirements-ai.txt의 패키지를 설치하세요.") from exc
    cache = configured_path(config, "AI_KNOWLEDGE", "preview_cache_folder", ".cache/ai_previews")
    cache.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256((source["sha256"] + ":" + str(page) + ":1800").encode("ascii")).hexdigest()
    target = cache / (digest + ".png")
    with _RENDER_LOCK:
        if not target.is_file():
            with pymupdf.open(original) as document:
                if document.needs_pass or page > len(document):
                    raise KnowledgeError("암호화되었거나 페이지 번호가 올바르지 않은 PDF입니다.")
                sheet = document[page - 1]
                scale = min(2.0, 1800 / max(sheet.rect.width, sheet.rect.height))
                pixels = sheet.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                temporary = target.with_suffix(".tmp")
                temporary.write_bytes(pixels.tobytes("png"))
                temporary.replace(target)
    return target


def original_image_path(config, identifier):
    _source, path = get_store(config).verified_source(identifier)
    if path.suffix.lower() not in IMAGE_FILES:
        raise KnowledgeError("이미지 자료가 아닙니다.")
    return path
