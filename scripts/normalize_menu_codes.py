from db_connection import get_db_connection
from permission_helpers import resolve_menu_code, MENU_PERMISSION_MAP

# 명시적인 메뉴 코드 매핑 (슬러그 -> 정규화 코드)
MENU_CODE_MAPPING = {
    slug: resolve_menu_code(slug)
    for slug in MENU_PERMISSION_MAP.keys()
}

# 추가적으로 정규화 함수가 처리할 수 있는 값들을 위해 역대칭
ADDITIONAL_CODES = {
    'vendor-management': 'VENDOR_MGT',
    'vendor_mgt': 'VENDOR_MGT',
}
MENU_CODE_MAPPING.update({k: v for k, v in ADDITIONAL_CODES.items() if v})


def normalize_table(cursor, table, key_columns):
    """주어진 테이블의 menu_code를 정규화한다.

    key_columns는 유니크 제약을 구성하는 컬럼 목록이다.
    슬러그와 정규화된 코드가 동시에 존재할 경우, 최대 권한을 유지한 뒤 슬러그 행을 제거한다.
    """
    columns = get_table_columns(cursor, table)

    for slug, normalized in MENU_CODE_MAPPING.items():
        if not normalized:
            continue

        # 1) 동일 키에 대해 슬러그와 정규화 코드가 모두 존재하면 권한을 병합
        if 'read_level' in columns or 'write_level' in columns:
            set_clause = []
            if 'read_level' in columns:
                set_clause.append('read_level = GREATEST(target.read_level, source.read_level)')
            if 'write_level' in columns:
                set_clause.append('write_level = GREATEST(target.write_level, source.write_level)')

            if set_clause:
                join_conditions = ' AND '.join([
                    f"target.{col} = source.{col}"
                    for col in key_columns
                ])
                sql = f"""
                    UPDATE {table} AS target
                    SET {', '.join(set_clause)}, updated_at = COALESCE(target.updated_at, source.updated_at)
                    FROM {table} AS source
                    WHERE target.menu_code = %s
                      AND source.menu_code = %s
                      AND {join_conditions}
                """
                params = [normalized, slug]
                cursor.execute(sql, params)

        # 2) 정규화된 레코드가 이미 존재하면 슬러그 레코드 제거
        join_conditions = ' AND '.join([
            f"{table}.{col} = other.{col}"
            for col in key_columns
        ])
        delete_sql = f"""
            DELETE FROM {table}
            USING {table} AS other
            WHERE {table}.menu_code = %s
              AND other.menu_code = %s
              AND {join_conditions}
        """
        cursor.execute(delete_sql, (slug, normalized))

        # 3) 남은 슬러그 값을 정규화 코드로 변환
        cursor.execute(
            f"UPDATE {table} SET menu_code = %s WHERE menu_code = %s",
            (normalized, slug),
        )


def get_table_columns(cursor, table):
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        """,
        (table,),
    )
    return {row[0] for row in cursor.fetchall() or []}


def normalize_menu_names(cursor):
    for slug, normalized in MENU_CODE_MAPPING.items():
        if not normalized:
            continue
        cursor.execute(
            """
            UPDATE menu_names
            SET menu_code = %s
            WHERE menu_code = %s
            """,
            (normalized, slug),
        )


def normalize_permission_requests(cursor):
    for slug, normalized in MENU_CODE_MAPPING.items():
        if not normalized:
            continue
        cursor.execute(
            """
            UPDATE permission_requests
            SET menu_code = %s
            WHERE menu_code = %s
            """,
            (normalized, slug),
        )


def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    normalize_table(cursor, 'user_menu_permissions', ['login_id'])
    normalize_table(cursor, 'dept_menu_permissions', ['dept_id'])
    normalize_table(cursor, 'dept_menu_roles', ['dept_id'])
    normalize_permission_requests(cursor)
    normalize_menu_names(cursor)

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
    print('Menu code normalization complete.')
