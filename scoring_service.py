"""
Scoring service: compute totals from dynamic scoring columns.

- Reads active 'scoring' and 'score_total' columns for a board
- scoring_config JSON format is described in 채점시스템_구현계획.md
"""
from __future__ import annotations

import json
from typing import Dict, Any, List, Tuple

import sqlite3
from db_connection import get_db_connection


DEFAULT_CRITERIA = {
    'critical': {'min': -999, 'max': -10, 'label': 'Critical'},
    'major': {'min': -9, 'max': -5, 'label': 'Major'},
    'minor': {'min': -4, 'max': -1, 'label': 'Minor'},
    'bonus': {'min': 0.1, 'max': 999, 'label': 'Bonus'},
}


def _normalize_board(board: str) -> str:
    m = board.strip().lower().replace('-', '_')
    # alias mapping if needed
    return m


def _load_columns(board: str, db_path: str) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path, row_factory=True)
    table = f"{board}_column_config"
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE (is_deleted = 0 OR is_deleted IS NULL) AND is_active = 1 ORDER BY column_order, id"
    ).fetchall()
    conn.close()
    cols: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        if d.get('scoring_config') and isinstance(d['scoring_config'], str):
            try:
                d['scoring_config'] = json.loads(d['scoring_config'])
            except Exception:
                pass
        cols.append(d)
    return cols


def _grade_for_per_unit(per_unit: float, criteria: Dict[str, Dict[str, float]]) -> str:
    for key, rng in criteria.items():
        if rng['min'] <= per_unit <= rng['max']:
            return key
    # default
    return 'minor' if per_unit < 0 else 'bonus'


def calculate_score(board: str, inputs: Dict[str, Any], db_path: str) -> Dict[str, Any]:
    """Compute score summary for the given board using current configs.

    inputs: mapping of field_key -> count (string or number). Field key must be
            formatted as f"{column_key}_{item['id']}" for scoring items.
    """
    board_norm = _normalize_board(board)
    cols = _load_columns(board_norm, db_path)

    # Base score detection: from any score_total column's scoring_config or default 100
    base_score = 100
    for c in cols:
        if c.get('column_type') == 'score_total' and isinstance(c.get('scoring_config'), dict):
            base_score = int(c['scoring_config'].get('base_score') or base_score)
            break

    # Criteria: from first scoring/score_total config that defines it or default
    criteria = DEFAULT_CRITERIA
    for c in cols:
        sc = c.get('scoring_config')
        if isinstance(sc, dict) and sc.get('grade_criteria'):
            criteria = sc['grade_criteria']
            break

    summary = {
        'critical_count': 0,
        'major_count': 0,
        'minor_count': 0,
        'bonus_points': 0,
        'total_delta': 0,
        'total_score': base_score,
        'base_score': base_score,
    }

    # Iterate all scoring items across all sections
    for c in cols:
        if c.get('column_type') != 'scoring':
            continue
        sc = c.get('scoring_config') or {}
        items = sc.get('items') or []
        for item in items:
            item_id = item.get('id')
            if not item_id:
                continue
            key = f"{c.get('column_key')}_{item_id}"
            raw = inputs.get(key, 0)
            try:
                count = int(str(raw).strip() or 0)
            except Exception:
                count = 0
            if count <= 0:
                continue
            per_unit = float(item.get('per_unit_delta') or 0)
            delta = int(count * per_unit)
            summary['total_delta'] += delta
            if per_unit > 0:
                summary['bonus_points'] += delta
            else:
                grade = _grade_for_per_unit(per_unit, criteria)
                if grade == 'critical':
                    summary['critical_count'] += count
                elif grade == 'major':
                    summary['major_count'] += count
                else:
                    summary['minor_count'] += count

    # Also include simple number columns that have per-column scoring config
    for c in cols:
        if c.get('column_type') != 'number':
            continue
        sc = c.get('scoring_config') or {}
        if isinstance(sc, str):
            try:
                sc = json.loads(sc)
            except Exception:
                sc = {}
        per_unit = sc.get('per_unit_delta')
        if per_unit is None:
            continue
        try:
            per_unit = float(per_unit)
        except Exception:
            continue
        key = c.get('column_key')
        raw = inputs.get(key, 0)
        try:
            count = int(str(raw).strip() or 0)
        except Exception:
            count = 0
        if count <= 0:
            continue
        delta = int(count * per_unit)
        summary['total_delta'] += delta
        if per_unit > 0:
            summary['bonus_points'] += delta
        else:
            # grade can be explicitly set or inferred from per_unit
            grade = sc.get('grade') or _grade_for_per_unit(per_unit, criteria)
            if grade == 'critical':
                summary['critical_count'] += count
            elif grade == 'major':
                summary['major_count'] += count
            else:
                summary['minor_count'] += count

    summary['total_score'] = base_score + summary['total_delta']
    return summary
