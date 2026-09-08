import configparser
import hashlib
import json
import logging
import math
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, abort, jsonify, render_template, request, send_file, session, url_for

import permission_helpers
from db_connection import get_db_connection
from permission_helpers import enforce_permission, get_user_permission_level
from upload_utils import sanitize_filename


PROJECT_ROOT = Path(__file__).resolve().parent
MENU_CODE = "AI_TRAINING_MATERIALS"
MATERIAL_PARTS = (
    "작업안전파트", "사고예방파트", "교육문화파트",
    "적격성평가파트", "위험성평가파트", "공통",
)
UNASSIGNED_PART = "__unassigned__"
ai_training_materials_bp = Blueprint("ai_training_materials", __name__)
logger = logging.getLogger(__name__)


class MaterialConflict(ValueError):
    pass


class NewUploadCopyError(OSError):
    pass


def load_settings():
    config = configparser.ConfigParser(interpolation=None)
    config.read(PROJECT_ROOT / "config.ini", encoding="utf-8")
    folder = Path(config.get("AI_TRAINING_MATERIALS", "upload_folder",
                             fallback="uploads/ai_training_materials"))
    if not folder.is_absolute():
        folder = PROJECT_ROOT / folder
    folder = folder.resolve()
    new_upload_value = config.get("AI_TRAINING_MATERIALS", "new_upload_folder",
                                  fallback="new_upload/ai_training_materials").strip()
    if not new_upload_value:
        raise ValueError("AI_TRAINING_MATERIALS.new_upload_folder 경로를 입력해 주세요.")
    new_upload_folder = Path(new_upload_value)
    if not new_upload_folder.is_absolute():
        new_upload_folder = PROJECT_ROOT / new_upload_folder
    new_upload_folder = new_upload_folder.resolve()
    if folder == new_upload_folder or folder in new_upload_folder.parents or new_upload_folder in folder.parents:
        raise ValueError("원본 저장 폴더와 new_upload 폴더는 서로 포함되지 않는 별도 경로여야 합니다.")
    limit = config.getint("AI_TRAINING_MATERIALS", "max_upload_size_mb", fallback=50)
    if limit <= 0:
        raise ValueError("AI_TRAINING_MATERIALS.max_upload_size_mb는 양수여야 합니다.")
    extensions = config.get("SECURITY", "allowed_extensions", fallback="pdf,docx,xlsx,pptx,txt")
    return {
        "folder": folder,
        "new_upload_folder": new_upload_folder,
        "max_mb": limit,
        "extensions": {value.strip().lower() for value in extensions.split(",") if value.strip()},
    }


def initialize_schema():
    with get_db_connection() as conn:
        for filename in ("008_create_ai_training_materials.sql", "009_add_ai_training_material_part.sql"):
            sql = (PROJECT_ROOT / "migrations" / filename).read_text(encoding="utf-8")
            conn.execute(sql)


def current_author():
    author_id = str(session.get("user_id") or "").strip()
    if not author_id and permission_helpers.PERMISSION_ENABLED:
        abort(401, description="로그인이 필요합니다.")
    return {
        "author_id": author_id or "DEV_USER",
        "author_name": str(session.get("user_name") or author_id or "개발 사용자"),
        "department_id": str(session.get("deptid") or session.get("dept_id") or ""),
        "department_name": str(session.get("deptname") or session.get("dept_name")
                               or session.get("department") or ""),
    }


def request_number(row):
    return "AI-{:%Y%m%d}-{:06d}".format(row["created_at"], row["id"])


def stored_path(relative_path, settings, *, new_upload=False):
    base_folder = settings["new_upload_folder"] if new_upload else settings["folder"]
    target = (base_folder / relative_path).resolve()
    try:
        target.relative_to(base_folder)
    except ValueError:
        raise ValueError("잘못된 첨부파일 경로입니다.")
    return target


def prepare_file(file_storage, settings):
    name = Path(file_storage.filename.replace("\\", "/")).name
    if not name or len(name) > 180:
        raise ValueError("파일명은 1~180자로 입력해 주세요.")
    if Path(name).suffix.lower().lstrip(".") not in settings["extensions"]:
        raise ValueError("허용되지 않은 파일 형식입니다: " + name)
    stream = file_storage.stream
    stream.seek(0)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > settings["max_mb"] * 1024 * 1024:
            raise ValueError("파일당 {}MB를 초과했습니다: {}".format(settings["max_mb"], name))
        digest.update(chunk)
    stream.seek(0)
    return {"file": file_storage, "name": name, "size": size, "sha256": digest.hexdigest()}


def build_import_key(prepared, folder_title=None):
    if folder_title is None:
        if len(prepared) != 1:
            raise ValueError("파일별 일괄 등록은 게시글당 파일 1개만 가능합니다.")
        return hashlib.sha256((prepared[0]["name"] + "\0" + prepared[0]["sha256"]).encode("utf-8")).hexdigest()
    if not prepared:
        raise ValueError("폴더에 첨부파일이 1개 이상 있어야 합니다.")
    manifest = [folder_title.strip(), sorted((item["name"], item["sha256"]) for item in prepared)]
    encoded = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "folder-v1:" + hashlib.sha256(encoded).hexdigest()


def remove_saved_files(paths):
    failed = []
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("학습자료 파일 정리 실패: %s", path)
            failed.append(path)
    for parent in {path.parent for path in paths}:
        try:
            parent.rmdir()
        except OSError:
            pass
    return failed


def save_material(title, files, author, material_id=None, keep_ids=None, version=None, import_key=None, part_name=None,
                  *, import_created_at=None, import_grouped=False, capture_new_uploads=False):
    title = str(title or "").strip()
    part_name = str(part_name or "").strip()
    if part_name not in MATERIAL_PARTS:
        raise ValueError("파트를 선택해 주세요. 공용 자료는 '공통'을 선택할 수 있습니다.")
    if not title or len(title) > 300:
        raise ValueError("제목은 1~300자로 입력해 주세요.")
    if not author.get("author_id") or not author.get("author_name"):
        raise ValueError("등록자 ID와 등록자명이 필요합니다.")
    if import_grouped and (import_key is None or material_id is not None):
        raise ValueError("폴더 묶음 등록은 신규 일괄 등록에만 사용할 수 있습니다.")
    if capture_new_uploads and import_key is not None:
        raise ValueError("일괄 등록 자료는 new_upload에 복사하지 않습니다.")
    if import_created_at is not None:
        if import_key is None or material_id is not None:
            raise ValueError("등록일 지정은 신규 일괄 등록에만 사용할 수 있습니다.")
        if not isinstance(import_created_at, datetime) or import_created_at.tzinfo is not None:
            raise ValueError("일괄 등록일은 시간대 없는 날짜·시각이어야 합니다.")
    settings = load_settings()
    prepared = [prepare_file(upload, settings) for upload in files if upload.filename]
    if import_key is not None:
        actual_key = build_import_key(prepared, folder_title=title if import_grouped else None)
        if import_key != actual_key:
            raise ValueError("검사 이후 원본 파일이 변경되었습니다. 다시 실행해 주세요.")
    new_paths = []
    removed_paths = []
    removed_new_uploads = []
    conn = get_db_connection()
    try:
        if material_id is None:
            if not prepared:
                raise ValueError("첨부파일을 1개 이상 추가해 주세요.")
            row = conn.execute(
                """INSERT INTO ai_training_materials
                   (title, author_id, author_name, department_id, department_name, updated_by, import_key, part_name,
                    created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                           COALESCE(%s::timestamp, CURRENT_TIMESTAMP), COALESCE(%s::timestamp, CURRENT_TIMESTAMP))
                   ON CONFLICT (import_key) DO NOTHING RETURNING *""",
                (title, author["author_id"], author["author_name"], author.get("department_id", ""),
                 author.get("department_name", ""), author["author_id"], import_key, part_name,
                 import_created_at, import_created_at),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None
            material_id = row["id"]
        else:
            row = conn.execute("SELECT * FROM ai_training_materials WHERE id = %s FOR UPDATE",
                               (material_id,)).fetchone()
            if row is None:
                raise ValueError("게시글이 존재하지 않습니다.")
            if row["updated_at"].isoformat() != version:
                raise MaterialConflict("다른 변경사항이 저장되었습니다. 창을 새로고침 후 다시 수정해 주세요.")
            existing = conn.execute("SELECT * FROM ai_training_material_files WHERE material_id = %s",
                                    (material_id,)).fetchall()
            if keep_ids is None or not set(keep_ids).issubset({item["id"] for item in existing}):
                raise ValueError("첨부파일 목록이 올바르지 않습니다.")
            if not keep_ids and not prepared:
                raise ValueError("첨부파일을 1개 이상 남겨 주세요.")
            for item in existing:
                if item["id"] not in keep_ids:
                    removed_paths.append(stored_path(item["storage_path"], settings))
                    if capture_new_uploads:
                        removed_new_uploads.append(stored_path(item["storage_path"], settings, new_upload=True))
                    conn.execute("DELETE FROM ai_training_material_files WHERE id = %s", (item["id"],))
            changed = title != row["title"] or part_name != row["part_name"] or bool(prepared) or bool(removed_paths)
            if changed:
                conn.execute("""UPDATE ai_training_materials SET title = %s, part_name = %s,
                             updated_at = clock_timestamp(), updated_by = %s WHERE id = %s""",
                             (title, part_name, author["author_id"], material_id))
        folder = settings["folder"] / request_number(row)
        if prepared:
            folder.mkdir(parents=True, exist_ok=True)
        for item in prepared:
            filename = uuid4().hex + "_" + sanitize_filename(item["name"])
            destination = stored_path(request_number(row) + "/" + filename, settings)
            new_paths.append(destination)
            item["file"].save(destination)
            if capture_new_uploads:
                pending_path = stored_path(request_number(row) + "/" + filename, settings, new_upload=True)
                new_paths.append(pending_path)
                try:
                    pending_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(destination, pending_path)
                except OSError as exc:
                    raise NewUploadCopyError("new_upload 파일 복사 실패") from exc
            conn.execute("""INSERT INTO ai_training_material_files
                         (material_id, file_name, storage_path, file_size, sha256)
                         VALUES (%s, %s, %s, %s, %s)""",
                         (material_id, item["name"], destination.relative_to(settings["folder"]).as_posix(),
                          item["size"], item["sha256"]))
        conn.commit()
    except Exception:
        conn.rollback()
        remove_saved_files(new_paths)
        raise
    finally:
        conn.close()
    failed_removals = remove_saved_files(removed_paths + removed_new_uploads)
    result = {"id": material_id, "request_number": request_number(row)}
    if failed_removals:
        result["warning"] = "게시글은 저장됐지만 이전 파일 일부를 폴더에서 삭제하지 못했습니다. 학습 전에 서버 로그에 표시된 파일과 폴더 권한을 확인해 주세요."
    return result


@ai_training_materials_bp.route("/ai-training-materials")
def materials_page():
    guard = enforce_permission(MENU_CODE, "view")
    if guard:
        return guard
    query = request.args.get("q", "").strip()
    selected_part = request.args.get("part", "").strip()
    if selected_part not in ("", UNASSIGNED_PART, *MATERIAL_PARTS):
        abort(400, description="올바른 파트를 선택해 주세요.")
    per_page = request.args.get("per_page", 10, type=int)
    if per_page not in (10, 25, 50, 100):
        per_page = 10
    page = max(1, request.args.get("page", 1, type=int))
    where_sql = "TRUE"
    params = ()
    if query:
        where_sql = "position(lower(%s) in lower(material.title)) > 0"
        params = (query,)
    if selected_part:
        where_sql += " AND material.part_name = %s"
        params += ("" if selected_part == UNASSIGNED_PART else selected_part,)
    with get_db_connection() as conn:
        total = conn.execute("SELECT count(*) AS total FROM ai_training_materials material WHERE " + where_sql,
                             params).fetchone()["total"]
        total_pages = max(1, math.ceil(total / per_page))
        page = min(page, total_pages)
        rows = conn.execute("SELECT material.* FROM ai_training_materials material WHERE " + where_sql +
                            " ORDER BY material.updated_at DESC, material.id DESC LIMIT %s OFFSET %s",
                            params + (per_page, (page - 1) * per_page)).fetchall()
    return render_template("ai-training-materials.html", materials=rows, query=query,
                           total_count=total, page=page, total_pages=total_pages, per_page=per_page,
                           selected_part=selected_part,
                           part_filters=[("", "전체")] + [(part, part) for part in MATERIAL_PARTS] + [(UNASSIGNED_PART, "미분류")],
                           register_part=selected_part if selected_part in MATERIAL_PARTS else "",
                           can_write=get_user_permission_level(MENU_CODE, "write") > 0)


@ai_training_materials_bp.route("/ai-training-materials/register")
def register_page():
    guard = enforce_permission(MENU_CODE, "edit")
    if guard:
        return guard
    return render_template("ai-training-material-detail.html", material=None, attachments=[],
                           author=current_author(), today=datetime.now(), settings=load_settings(),
                           parts=MATERIAL_PARTS,
                           selected_part=request.args.get("part") if request.args.get("part") in MATERIAL_PARTS else "",
                           can_write=True, is_popup=request.args.get("popup") == "1")


@ai_training_materials_bp.route("/ai-training-materials/<int:material_id>")
def detail_page(material_id):
    guard = enforce_permission(MENU_CODE, "view")
    if guard:
        return guard
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM ai_training_materials WHERE id = %s", (material_id,)).fetchone()
        if row is None:
            abort(404)
        attachments = conn.execute("SELECT * FROM ai_training_material_files WHERE material_id = %s ORDER BY id",
                                   (material_id,)).fetchall()
    return render_template("ai-training-material-detail.html", material=row, attachments=attachments,
                           request_number=request_number(row), settings=load_settings(),
                           parts=MATERIAL_PARTS, selected_part=row["part_name"],
                           can_write=get_user_permission_level(MENU_CODE, "write") > 0,
                           is_popup=request.args.get("popup") == "1")


@ai_training_materials_bp.route("/api/ai-training-materials", methods=["POST"])
@ai_training_materials_bp.route("/api/ai-training-materials/<int:material_id>", methods=["POST"])
def save_api(material_id=None):
    guard = enforce_permission(MENU_CODE, "edit", response_type="json")
    if guard:
        return guard
    author = current_author()
    try:
        keep_ids = None
        if material_id is not None:
            keep_ids = json.loads(request.form.get("keep_file_ids", "null"))
            if not isinstance(keep_ids, list) or any(type(value) is not int for value in keep_ids):
                raise ValueError("첨부파일 목록이 올바르지 않습니다.")
        saved = save_material(request.form.get("title"), request.files.getlist("files"), author,
                              material_id=material_id, keep_ids=keep_ids, version=request.form.get("version"),
                              part_name=request.form.get("part_name"), capture_new_uploads=True)
        return jsonify(success=True, **saved, detail_url=url_for("ai_training_materials.detail_page", material_id=saved["id"]))
    except MaterialConflict as exc:
        return jsonify(success=False, message=str(exc)), 409
    except ValueError as exc:
        return jsonify(success=False, message=str(exc)), 400
    except NewUploadCopyError:
        logger.exception("AI 학습자료 new_upload 복사 실패; 저장 취소")
        return jsonify(success=False, message="새 업로드 폴더(new_upload)에 복사하지 못해 저장을 취소했습니다. 폴더 경로·쓰기 권한·디스크 여유 공간을 확인해 주세요."), 500
    except Exception:
        logger.exception("AI 학습자료 저장 실패")
        return jsonify(success=False, message="저장하지 못했습니다. 서버 로그와 파일 저장 폴더 권한을 확인해 주세요."), 500


@ai_training_materials_bp.route("/ai-training-materials/files/<int:file_id>/download")
def download_file(file_id):
    guard = enforce_permission(MENU_CODE, "view")
    if guard:
        return guard
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM ai_training_material_files WHERE id = %s", (file_id,)).fetchone()
    if row is None:
        abort(404)
    path = stored_path(row["storage_path"], load_settings())
    if not path.is_file():
        abort(404, description="첨부파일이 저장 폴더에 없습니다.")
    return send_file(path, as_attachment=True, download_name=row["file_name"])
