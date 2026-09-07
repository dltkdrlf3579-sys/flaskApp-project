import argparse
import configparser
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from portal_ai.knowledge import KnowledgeStore, KnowledgeError, digest_file
from portal_ai.settings import load_config


def collect_files(store):
    store.assert_unchanged()
    files = {}

    def add(relative, expected=None, optional=False):
        normalized = str(relative).replace("\\", "/")
        if PurePosixPath(normalized).is_absolute() or ".." in PurePosixPath(normalized).parts or ":" in normalized:
            raise KnowledgeError("자료 목록의 상대경로가 올바르지 않습니다.")
        path = store.root / normalized
        if not path.is_file():
            if optional:
                return
            raise KnowledgeError("묶음에 필요한 파일이 없습니다: " + normalized)
        actual = digest_file(path)
        if expected and expected != actual:
            raise KnowledgeError("원본 버전이 등록 목록과 다릅니다: " + normalized)
        files[normalized] = {"path": path, "sha256": actual, "size": path.stat().st_size}

    add(store.index_path.relative_to(store.root).as_posix())
    for domain in store.domains:
        add("knowledge/{}/source_registry.json".format(domain))
    for source in store.sources.values():
        add(source["relative_path"], source["sha256"])
        for download in source["downloads"]:
            add(download["relative_path"])
    add("public_downloads/_catalog.json", optional=True)
    prefix = "artifacts/document_understanding/"
    for identifiers in store.page_artifacts.values():
        for artifact_id in identifiers:
            relative = prefix + "pages/" + artifact_id + ".json"
            path = store.root / relative
            if not path.is_file():
                continue
            metadata = json.loads(path.read_text(encoding="utf-8-sig"))
            image = str(metadata.get("page_image_path") or "")
            if metadata.get("artifact_id") != artifact_id or not image.startswith("images/pages/"):
                continue
            add(relative)
            add(prefix + image)
    store.assert_unchanged()
    return files


def write_package(store, destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise KnowledgeError("출력 파일이 이미 있습니다. 새 파일명을 지정하세요.")
    files = collect_files(store)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    if temporary.exists():
        raise KnowledgeError("동일한 이름의 작업 중 파일이 있습니다. 다른 출력 이름을 지정하세요.")
    manifest = {"format": 1, "domains": list(store.domains), "files": []}
    try:
        with zipfile.ZipFile(temporary, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for relative, item in files.items():
                digest = hashlib.sha256()
                with item["path"].open("rb") as source, archive.open(relative, "w", force_zip64=True) as target:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                        target.write(chunk)
                if digest.hexdigest() != item["sha256"]:
                    raise KnowledgeError("압축 도중 자료가 변경되었습니다. 자료 갱신을 마친 뒤 다시 실행하세요.")
                manifest["files"].append({"path": relative, "sha256": item["sha256"], "size": item["size"]})
            archive.writestr("portal_bundle_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip():
                raise KnowledgeError("압축 파일 검사에 실패했습니다.")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return len(files), sum(item["size"] for item in files.values())


def check_install(config):
    store = KnowledgeStore(config)
    for identifier in store.sources:
        store.verified_source(identifier)
    files = collect_files(store)
    manifest_path = store.root / "portal_bundle_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        for item in manifest["files"]:
            path = (store.root / item["path"]).resolve()
            if store.root not in path.parents or not path.is_file() or digest_file(path) != item["sha256"]:
                raise KnowledgeError("이관 파일 검증 실패: " + item["path"])
    else:
        print("NOTE: no transfer manifest; registered original hashes were checked.")
    print("OK: {} sources, {} indexed chunks, {} bundle files".format(len(store.sources), len(store.chunks), len(files)))
    import requests
    import pymupdf
    print("OK: requests {}, PyMuPDF {}".format(requests.__version__, pymupdf.VersionBind))
    if config.get("AI_ASSISTANT", "mode", fallback="mock").lower() in {"internal", "real"}:
        from portal_ai.routing import ModelRouting
        ModelRouting(config)
        print("OK: required internal API settings present (network NOT tested)")
    print("No AI calls, DB writes or index rebuild performed.")


def main():
    parser = argparse.ArgumentParser(description="Package existing approved Kakao materials for the portal. No AI calls or re-indexing.")
    parser.add_argument("--source-root")
    parser.add_argument("--domains", default="safety_training,safety_law")
    parser.add_argument("--output")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            if args.output or args.source_root:
                parser.error("--check reads portal config.ini; do not combine with --source-root/--output")
            check_install(load_config())
        else:
            if not args.source_root or not args.output:
                parser.error("--source-root and --output are required")
            config = configparser.ConfigParser(interpolation=None)
            config["AI_KNOWLEDGE"] = {"root_folder": str(Path(args.source_root).resolve()), "domains": args.domains}
            store = KnowledgeStore(config)
            count, size = write_package(store, args.output)
            print("OK: {} files, {:.1f} MB before compression -> {}".format(count, size / 1024 ** 2, Path(args.output).resolve()))
    except (KnowledgeError, OSError, ValueError, ImportError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
