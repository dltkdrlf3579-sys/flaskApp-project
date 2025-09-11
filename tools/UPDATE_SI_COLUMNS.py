#!/usr/bin/env python3
"""
Standardize safety_instruction_column_config labels and ensure linked base/sibling keys exist.

What it does:
- Updates column_name (labels) per provided mapping
- Ensures important base/sibling keys exist to enable linked popups via suffix inference
- Leaves tab/section/order intact for existing rows (new keys appended at the end)

Usage:
  python tools/UPDATE_SI_COLUMNS.py

Idempotent; safe to run multiple times.
"""
from db_connection import get_db_connection
from db.upsert import safe_upsert


# Key → Label mapping
LABELS = {
    # 기본/식별
    'issue_number': '발부번호',
    'created_at': '등록일',

    # 발행인(담당자) 링크 세트
    'issuer': '발행인(이름)',
    'issuer_id': '발행인 ID',
    'issuer_dept': '발행부서',

    # 분류/고용형태
    'classification': '분류',
    'employment_type': '고용형태',
    'employement_type': '고용형태',  # typo variant

    # 1차사 링크 세트
    'primary_company': '1차사명',
    'primary_company_bizno': '1차사명 사업자번호',

    # 하도사 링크 세트(일부 환경에서는 secondary_company 대신 subcontractor 사용)
    'secondary_company': '하도사명',
    'secondary_company_bizno': '하도사명 사업자번호',
    'subcontractor': '하도사명',
    'subcontractor_business_number': '하도사명 사업자번호',

    # 징계대상자(협력사 근로자) 링크 세트 – 철자를 폭넓게 수용
    'disciplined_person': '징계대상자 성함',
    'disciplined_person_id': 'PCMS ID',
    'discipled_person_id': 'PCMS ID',
    'displined_person_id': 'PCMS ID',
    'disciplined_person_company': '징계대상자 소속업체',
    'disciplined_person_bizno': '소속업체 사업자번호',

    # 기타 기본 정보
    'birth': '생년월일',
    'GBM': 'GBM',
    'business_division': '사업부',
    'team': '팀',
    'dept': '소속부서',

    # 위반/징계
    'violation_date': '위반일자',
    'discipline_date': '징계일자',
    'discipline_type': '징계유형',
    'displine_type': '징계유형',  # typo variant

    # 사고 연계
    'accident_number': '사고번호',
    'accident_type': '사고유형',
    'accident_grade': '사고등급',

    # 위반 상세
    'violation_grade': '환경안전수칙 위반등급',
    'violation_type': '위반유형',
    'violation_content': '위반내용',

    # 출입정지
    'access_ban_start_date': '출입정지 시작일',
    'access_ban_end_date': '출입정지 종료일',
    'period': '기간',
    'work_grade': '작업등급',
    'penalty_points': '감점',
    # 추가: 징계 발의부서 (부서 선택 팝업)
    'issuer_incharge_dept': '징계 발의부서',
}


# Grouped keys to ensure base/sibling presence (for popup inference via suffix)
GROUPS = [
    # person: base has _dept sibling
    ['issuer', 'issuer_dept', 'issuer_id'],
    # company: base has _bizno sibling
    ['primary_company', 'primary_company_bizno'],
    ['secondary_company', 'secondary_company_bizno'],
    ['subcontractor', 'subcontractor_business_number'],
    # contractor: base may use *_company or dedicate disciplined person set
    ['disciplined_person', 'disciplined_person_id', 'disciplined_person_company', 'disciplined_person_bizno'],
]


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch existing keys and max order
    try:
        rows = cur.execute("SELECT column_key, column_order FROM safety_instruction_column_config").fetchall()
        existing = { (r[0] if not hasattr(r, 'keys') else r['column_key']).lower(): (r[1] if not hasattr(r, 'keys') else r['column_order']) for r in rows }
        max_order = max([v for v in existing.values() if isinstance(v, int)], default=0)
    except Exception:
        existing = {}
        max_order = 0

    # Upsert labels
    updated = 0
    created = 0
    for key, label in LABELS.items():
        key_norm = key.lower()
        data = {
            'column_key': key_norm,
            'column_name': label,
            'column_type': 'text',
            'is_active': 1,
            'is_deleted': 0,
        }
        # 특정 키는 명시적으로 팝업 타입 지정
        if key_norm == 'issuer_incharge_dept':
            data['column_type'] = 'popup_department'
        # Preserve existing order; assign next for new keys
        if key_norm in existing:
            # do not override column_order if exists
            pass
        else:
            max_order += 1
            data['column_order'] = max_order

        # Upsert
        rc = safe_upsert(
            conn,
            'safety_instruction_column_config',
            data,
            conflict_cols=['column_key'],
            update_cols=['column_name', 'column_type', 'is_active', 'is_deleted', 'updated_at'] + (['column_order'] if 'column_order' in data else [])
        )
        if key_norm in existing:
            updated += 1
        else:
            created += 1

    # Ensure base/sibling presence for popup inference
    ensured = 0
    for group in GROUPS:
        for key in group:
            key_norm = key.lower()
            if key_norm not in existing:
                max_order += 1
                label = LABELS.get(key, key)
                data = {
                    'column_key': key_norm,
                    'column_name': label,
                    'column_type': 'text',
                    'is_active': 1,
                    'is_deleted': 0,
                    'column_order': max_order,
                }
                safe_upsert(
                    conn,
                    'safety_instruction_column_config',
                    data,
                    conflict_cols=['column_key'],
                    update_cols=['column_name', 'column_type', 'is_active', 'is_deleted', 'column_order', 'updated_at']
                )
                ensured += 1

    conn.commit()
    conn.close()

    print(f"safety_instruction_column_config updated. labels updated={updated}, created={created}, ensured_siblings={ensured}")


if __name__ == '__main__':
    main()
