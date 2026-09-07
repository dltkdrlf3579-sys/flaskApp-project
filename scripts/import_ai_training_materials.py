import argparse
import hashlib
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import one file as one AI training material post. Preview by default.")
    parser.add_argument("--folder", type=Path, help="Source folder; originals are copied, never moved.")
    parser.add_argument("--recursive", action="store_true", help="Include subfolders.")
    parser.add_argument("--author-id", help="Author SSO ID.")
    parser.add_argument("--author-name", help="Author display name.")
    parser.add_argument("--department", help="Author department name.")
    parser.add_argument("--department-id", default="", help="Author department code (optional).")
    parser.add_argument("--apply", action="store_true", help="Create posts and copy files; omitted means preview only.")
    parser.add_argument("--init-only", action="store_true", help="Create only this board's tables, then exit.")
    args = parser.parse_args(argv)
    source = args.folder.resolve() if args.folder else None
    if not args.init_only and (source is None or not source.is_dir()):
        parser.error("--folder must point to an existing directory.")
    if args.apply and not args.init_only and not all((args.author_id, args.author_name, args.department)):
        parser.error("--apply requires --author-id, --author-name and --department.")
    previous_cwd = Path.cwd()
    try:
        os.chdir(PROJECT_ROOT)
        from werkzeug.datastructures import FileStorage
        from ai_training_materials import initialize_schema, load_settings, prepare_file, save_material
        from db_connection import get_db_connection

        if args.init_only:
            initialize_schema()
            print("AI training material tables are ready (team PostgreSQL).")
            return 0
        settings = load_settings()
        destination = settings["folder"]
        if source == destination or source in destination.parents or destination in source.parents:
            parser.error("Source and upload folders must be separate, not nested inside each other.")
        paths = sorted((source.rglob("*") if args.recursive else source.iterdir()), key=lambda path: str(path).casefold())
        paths = [path for path in paths if path.is_file() and not path.is_symlink()]
        print("Source:", source)
        print("Upload folder:", destination)
        print("Mode:", "APPLY" if args.apply else "PREVIEW (no DB/file changes)")
        if args.apply:
            initialize_schema()
            with get_db_connection() as conn:
                target = conn.execute("SELECT current_database() AS name, inet_server_addr()::text AS host").fetchone()
                print("Team PostgreSQL:", target["name"], target["host"])
        created = skipped = failed = 0
        for path in paths:
            try:
                with path.open("rb") as stream:
                    upload = FileStorage(stream=stream, filename=path.name)
                    prepared = prepare_file(upload, settings)
                    if not args.apply:
                        print("[READY]", path.name, "-> title:", path.name)
                        continue
                    import_key = hashlib.sha256((path.name + "\0" + prepared["sha256"]).encode("utf-8")).hexdigest()
                    saved = save_material(path.name, [upload], {
                        "author_id": args.author_id.strip(), "author_name": args.author_name.strip(),
                        "department_id": args.department_id.strip(), "department_name": args.department.strip(),
                    }, import_key=import_key)
                    if saved is None:
                        skipped += 1
                        print("[SKIP unchanged]", path.name)
                    else:
                        created += 1
                        print("[CREATED]", saved["request_number"], path.name)
            except Exception as exc:
                failed += 1
                print("[FAILED]", path.name, str(exc))
        print("Files: {}; created: {}; skipped: {}; failed: {}".format(len(paths), created, skipped, failed))
        return 1 if failed else 0
    finally:
        os.chdir(previous_cwd)


if __name__ == "__main__":
    raise SystemExit(main())
