import argparse
import os
import sys
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

PART_AUTHOR_IDS = {
    "작업안전파트": "kamarad.kim",
    "사고예방파트": "sang0.oh",
    "위험성평가파트": "dgyeong.kwak",
    "교육문화파트": "ks72.lim",
    "적격성평가파트": "sanggil2.lee",
}


def parse_created_date(value):
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        if parsed.strftime("%Y-%m-%d") != value:
            raise ValueError()
        return parsed
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--created-date는 YYYY-MM-DD 형식의 실제 날짜여야 합니다.") from exc


def lookup_part_author(part):
    author_id = PART_AUTHOR_IDS.get(part)
    if not author_id:
        raise ValueError("이 파트는 지정 담당자가 없습니다. 공통 자료는 --author-id, --author-name, --department를 직접 지정하세요.")
    from db_connection import get_db_connection

    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                """SELECT login_id, user_name, dept_id, dept_name, is_active
                   FROM system_users WHERE lower(btrim(login_id)) = lower(%s) LIMIT 2""",
                (author_id,),
            ).fetchall()
    except Exception as exc:
        raise ValueError("팀 DB의 system_users 조회에 실패했습니다. DB 연결과 사용자 정보 동기화 상태를 확인하세요.") from exc
    if not rows:
        raise ValueError("system_users에 담당자 ID가 없습니다: " + author_id + ". 사용자 정보 동기화 후 다시 실행하세요.")
    if len(rows) != 1:
        raise ValueError("system_users에 담당자 ID가 중복되어 있습니다: " + author_id)
    row = rows[0]
    if row["is_active"] is not True:
        raise ValueError("비활성 담당자는 등록자로 지정할 수 없습니다: " + author_id)
    author = {
        "author_id": str(row["login_id"] or "").strip(),
        "author_name": str(row["user_name"] or "").strip(),
        "department_id": str(row["dept_id"] or "").strip(),
        "department_name": str(row["dept_name"] or "").strip(),
    }
    missing = [key for key, value in author.items() if not value]
    if missing:
        raise ValueError("담당자 정보가 누락되었습니다: " + author_id + " (" + ", ".join(missing) + ")")
    return author


def collect_files(folder, recursive=False):
    paths = folder.rglob("*") if recursive else folder.iterdir()
    return sorted((path for path in paths if path.is_file() and not path.is_symlink()),
                  key=lambda path: str(path).casefold())


def collect_import_groups(source, group_by_folder=False, recursive=False):
    if not group_by_folder:
        return [(path.name, [path], False) for path in collect_files(source, recursive)]
    groups = []
    for path in sorted(source.iterdir(), key=lambda path: str(path).casefold()):
        if path.is_symlink():
            continue
        if path.is_file():
            groups.append((path.name, [path], False))
        elif path.is_dir():
            groups.append((path.name, collect_files(path, recursive=True), True))
    return groups


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import AI training materials by file or folder. Preview by default.")
    parser.add_argument("--folder", type=Path, help="Source folder; originals are copied, never moved.")
    grouping = parser.add_mutually_exclusive_group()
    grouping.add_argument("--recursive", action="store_true", help="Include subfolders; still one post per file.")
    grouping.add_argument("--group-by-folder", action="store_true", help="Each immediate subfolder becomes one post with all its files (including deeper folders). Loose files remain separate posts.")
    parser.add_argument("--author-id", help="Author SSO ID.")
    parser.add_argument("--author-name", help="Author display name.")
    parser.add_argument("--department", help="Author department name.")
    parser.add_argument("--part", help="Material part, e.g. 작업안전파트 or 공통 (required except --init-only).")
    parser.add_argument("--department-id", default="", help="Author department code (optional).")
    parser.add_argument("--use-part-author", action="store_true", help="Look up the assigned part owner's name/department in team DB system_users.")
    parser.add_argument("--created-date", type=parse_created_date, help="New imports only: registration and initial modified date (YYYY-MM-DD, midnight). Omit for current time.")
    parser.add_argument("--apply", action="store_true", help="Create posts and copy files; omitted means preview only.")
    parser.add_argument("--init-only", action="store_true", help="Create only this board's tables, then exit.")
    args = parser.parse_args(argv)
    source = args.folder.resolve() if args.folder else None
    if not args.init_only and (source is None or not source.is_dir()):
        parser.error("--folder must point to an existing directory.")
    if not args.init_only:
        if args.use_part_author and (any(value is not None for value in (args.author_id, args.author_name, args.department)) or args.department_id):
            parser.error("--use-part-author cannot be combined with manual author/department arguments.")
        if args.apply and not args.use_part_author and not all(str(value or "").strip() for value in (args.author_id, args.author_name, args.department)):
            parser.error("--apply requires --use-part-author or --author-id, --author-name and --department.")
    previous_cwd = Path.cwd()
    try:
        os.chdir(PROJECT_ROOT)
        from werkzeug.datastructures import FileStorage
        from ai_training_materials import MATERIAL_PARTS, build_import_key, initialize_schema, load_settings, prepare_file, save_material
        from db_connection import get_db_connection

        if args.init_only:
            initialize_schema()
            print("AI training material tables are ready (team PostgreSQL).")
            return 0
        if args.part not in MATERIAL_PARTS:
            parser.error("--part must be one of: " + ", ".join(MATERIAL_PARTS))
        settings = load_settings()
        destination = settings["folder"]
        if source == destination or source in destination.parents or destination in source.parents:
            parser.error("Source and upload folders must be separate, not nested inside each other.")
        groups = collect_import_groups(source, args.group_by_folder, args.recursive)
        if args.use_part_author:
            try:
                author = lookup_part_author(args.part)
            except ValueError as exc:
                print("[ERROR]", str(exc), file=sys.stderr)
                return 1
        else:
            author = {
                "author_id": str(args.author_id or "").strip(), "author_name": str(args.author_name or "").strip(),
                "department_id": args.department_id.strip(), "department_name": str(args.department or "").strip(),
            }
        print("Source:", source)
        print("Upload folder:", destination)
        print("Part:", args.part)
        print("Author:", author["author_id"], author["author_name"])
        print("Department:", author["department_id"], author["department_name"])
        print("Created / initial modified:", args.created_date.isoformat(sep=" ") if args.created_date else "current time")
        print("Mode:", "APPLY" if args.apply else "PREVIEW (no DB/file changes)")
        print("Grouping:", "one post per immediate subfolder; loose files separately" if args.group_by_folder else "one post per file")
        if args.apply:
            initialize_schema()
            with get_db_connection() as conn:
                target = conn.execute("SELECT current_database() AS name, inet_server_addr()::text AS host").fetchone()
                print("Team PostgreSQL:", target["name"], target["host"])
        created = skipped = failed = 0
        for title, paths, grouped in groups:
            if not paths:
                print("[SKIP empty folder]", title)
                continue
            try:
                with ExitStack() as opened:
                    uploads = []
                    for path in paths:
                        stream = opened.enter_context(path.open("rb"))
                        uploads.append(FileStorage(stream=stream, filename=path.name))
                    prepared = [prepare_file(upload, settings) for upload in uploads]
                    import_key = build_import_key(prepared, folder_title=title if grouped else None)
                    if not args.apply:
                        print("[READY] title:", title, "| attachments:", len(paths))
                        for path in paths:
                            print("  -", path.relative_to(source))
                        continue
                    saved = save_material(title, uploads, author, import_key=import_key, part_name=args.part,
                                          import_created_at=args.created_date, import_grouped=grouped)
                    if saved is None:
                        skipped += 1
                        print("[SKIP unchanged]", title)
                    else:
                        created += 1
                        print("[CREATED]", saved["request_number"], title, "| attachments:", len(paths))
            except Exception as exc:
                failed += 1
                print("[FAILED]", title, str(exc))
        print("Files: {}; created: {}; skipped: {}; failed: {}".format(sum(len(paths) for _, paths, _ in groups), created, skipped, failed))
        return 1 if failed else 0
    finally:
        os.chdir(previous_cwd)


if __name__ == "__main__":
    raise SystemExit(main())
