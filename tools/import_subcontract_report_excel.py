#!/usr/bin/env python3
"""
Excel → subcontract_report 데이터 이관 스크립트.

1. xlwings로 엑셀을 강제로 열어 원본 서식을 그대로 읽어옵니다.
2. submission_date를 created_at으로 간주하고 SRyyMMdd### 형식의 report_number를 생성합니다.
3. 나머지 컬럼은 custom_data(JSONB)로 직렬화한 뒤 subcontract_report 테이블에 upsert 합니다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import xlwings as xw
from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

DEFAULT_DB_URL = os.environ.get(
    "PORTAL_DATABASE_URL",
    "postgresql+psycopg2://adminuser:password@0.0.0.0:5432/servername",
)

EXCEL_DATE_COLUMNS = {
    "submission_date",
    "subcontract_start_date",
    "subcontract_end_date",
    "accept_date",
}


def _log(msg: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def _normalize_column(name: Any) -> str:
    if name is None:
        return ""
    text = str(name).strip()
    if not text:
        return ""
    text = (
        text.replace(" ", "_")
        .replace(".", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("-", "_")
    )
    while "__" in text:
        text = text.replace("__", "_")
    return text.lower()


def load_excel_via_xlwings(path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
    _log(f"Opening Excel via xlwings: {path}")
    app = xw.App(visible=False)
    try:
        wb = xw.Book(path)
        sheet = wb.sheets[sheet_name] if sheet_name else wb.sheets[0]
        df = sheet.used_range.options(pd.DataFrame, header=1, index=False).value
        wb.close()
        return df
    finally:
        app.quit()


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.dropna(how="all")
    df = df.loc[:, ~df.columns.isnull()]
    df.columns = [_normalize_column(col) for col in df.columns]
    df = df.loc[:, [col for col in df.columns if col]]
    df = df.replace({pd.NaT: None, pd.NA: None})
    return df


def parse_excel_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", "nan"):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        # pandas/Excel serial date → timestamp
        try:
            return pd.to_datetime(value, unit="D", origin="1899-12-30").to_pydatetime().replace(
                tzinfo=timezone.utc
            )
        except Exception:
            return None
    try:
        parsed = pd.to_datetime(str(value))
        return parsed.to_pydatetime().replace(tzinfo=timezone.utc)
    except Exception:
        return None


def generate_report_number_tracker() -> Dict[str, int]:
    return defaultdict(int)


def next_report_number(tracker: Dict[str, int], created_at: datetime) -> str:
    date_key = created_at.strftime("%y%m%d")
    tracker[date_key] += 1
    return f"SR{date_key}{tracker[date_key]:03d}"


def row_to_custom_data(row: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key, value in row.items():
        if key in {"created_at"}:
            continue
        if value in (None, "", [], {}):
            continue
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
        elif isinstance(value, (list, dict)):
            payload[key] = value
        else:
            payload[key] = value
    return payload


def build_records(
    df: pd.DataFrame,
    created_by: str,
    updated_by: str,
) -> Iterable[Dict[str, Any]]:
    tracker = generate_report_number_tracker()
    utcnow = datetime.now(timezone.utc)

    for idx, row in enumerate(df.to_dict(orient="records"), start=1):
        submission_dt = parse_excel_datetime(row.get("submission_date"))
        created_at = submission_dt or utcnow
        report_number = next_report_number(tracker, created_at)

        for key in EXCEL_DATE_COLUMNS:
            if key in row:
                row[key] = parse_excel_datetime(row[key]) or row[key]

        custom_data = row_to_custom_data(row)

        yield {
            "report_number": report_number,
            "custom_data": custom_data,
            "is_deleted": 0,
            "created_at": created_at,
            "created_by": created_by,
            "updated_at": created_at,
            "updated_by": updated_by,
        }


def upsert_records(engine, records: Iterable[Dict[str, Any]], dry_run: bool) -> None:
    metadata = MetaData()
    metadata.reflect(engine, only=["subcontract_report"])
    table = Table("subcontract_report", metadata, autoload_with=engine)

    total = 0
    with engine.begin() as conn:
        for chunk_start, record in enumerate(records, start=1):

            stmt = pg_insert(table).values(record)
            stmt = stmt.on_conflict_do_update(
                index_elements=["report_number"],
                set_={
                    "custom_data": stmt.excluded.custom_data,
                    "updated_at": stmt.excluded.updated_at,
                    "updated_by": stmt.excluded.updated_by,
                },
            )
            if dry_run:
                _log(f"[DRY-RUN] Would upsert report_number={record['report_number']}")
            else:
                conn.execute(stmt)
            total = chunk_start
    _log(f"Processed {total} rows ({'dry-run' if dry_run else 'committed'}).")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import subcontract_report data from Excel.")
    parser.add_argument("excel_path", help="Excel 파일 경로")
    parser.add_argument(
        "--sheet",
        dest="sheet_name",
        default=None,
        help="읽어올 시트명 (미지정 시 첫 번째 시트)",
    )
    parser.add_argument(
        "--db-url",
        dest="db_url",
        default=DEFAULT_DB_URL,
        help=f"SQLAlchemy DB URL (default: {DEFAULT_DB_URL})",
    )
    parser.add_argument(
        "--created-by",
        dest="created_by",
        default="excel_migration",
        help="created_by / updated_by에 기록할 값",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 쓰지 않고 생성될 report_number와 변환 결과만 로그로 출력",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    df_raw = load_excel_via_xlwings(args.excel_path, args.sheet_name)
    df = clean_dataframe(df_raw)

    if df.empty:
        _log("엑셀에 데이터가 없습니다. 종료합니다.")
        return

    _log(f"Loaded {len(df)} rows (columns={list(df.columns)})")

    records = list(
        build_records(
            df=df,
            created_by=args.created_by,
            updated_by=args.created_by,
        )
    )

    if args.dry_run:
        _log("=== DRY RUN SAMPLE ===")
        for sample in records[:3]:
            _log(json.dumps(sample, ensure_ascii=False, default=str))

    engine = create_engine(args.db_url, future=True)
    upsert_records(engine, records, dry_run=args.dry_run)


if __name__ == "__main__":
    main(sys.argv[1:])
