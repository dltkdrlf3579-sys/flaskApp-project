# db/compat.py - v7 호환 레이어 구현
import sqlite3
import re
import json

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    PSYCOPG_AVAILABLE = True
    PSYCOPG_VERSION = 3
except ImportError:
    try:
        import psycopg2
        import psycopg2.extras
        PSYCOPG_AVAILABLE = True
        PSYCOPG_VERSION = 2
        # psycopg2 호환성을 위한 alias
        class dict_row:
            @staticmethod
            def __call__(cursor):
                return psycopg2.extras.RealDictCursor
        class Jsonb:
            def __init__(self, obj):
                self.obj = json.dumps(obj) if not isinstance(obj, str) else obj
    except ImportError:
        PSYCOPG_AVAILABLE = False
        PSYCOPG_VERSION = None


class SqliteRowCompat:
    """SQLite Row 호환 클래스 - dict와 인덱스 접근 모두 지원"""
    def __init__(self, data_dict, keys):
        self._dict = data_dict
        self._keys = list(keys)
    
    def __getitem__(self, key):
        if isinstance(key, int):
            # 인덱스 접근: row[0]
            if 0 <= key < len(self._keys):
                dict_key = self._keys[key]
                return self._dict[dict_key]
            else:
                raise IndexError("row index out of range")
        else:
            # 키 접근: row['column']
            return self._dict[key]
    
    def keys(self):
        return self._keys
    
    def values(self):
        return [self._dict[k] for k in self._keys]
    
    def items(self):
        return [(k, self._dict[k]) for k in self._keys]
    
    def __len__(self):
        return len(self._keys)
    
    def __iter__(self):
        return iter(self._keys)


class EmptyResult:
    """PRAGMA no-op용 빈 결과"""
    def fetchone(self):
        return None
    def fetchall(self):
        return []
    def fetchmany(self, size=None):
        return []


class CompatConnection:
    """SQLite API를 완벽 에뮬레이션하는 통합 연결 래퍼 - v7"""
    
    def __init__(self, backend='sqlite', **kwargs):
        self.backend = backend
        self._row_factory = None
        self._in_transaction = False
        
        if backend == 'postgres':
            if not PSYCOPG_AVAILABLE:
                raise ImportError("psycopg not available - cannot connect to PostgreSQL")
            
            # PostgreSQL 연결
            if PSYCOPG_VERSION == 3:
                self._conn = psycopg.connect(
                    kwargs.get('dsn'),
                    row_factory=dict_row,
                    client_encoding='UTF8'
                )
            else:  # psycopg2
                import psycopg2
                import psycopg2.extras
                self._conn = psycopg2.connect(
                    kwargs.get('dsn'),
                    cursor_factory=psycopg2.extras.RealDictCursor
                )
            self.is_postgres = True
        else:
            # SQLite 연결
            self._conn = sqlite3.connect(
                kwargs.get('database', 'portal.db'),
                timeout=kwargs.get('timeout', 10.0)
            )
            self.is_postgres = False
            self._setup_sqlite_pragmas()
    
    def _setup_sqlite_pragmas(self):
        """SQLite PRAGMA 설정"""
        pragmas = [
            "PRAGMA foreign_keys=ON",
            "PRAGMA journal_mode=WAL",
            "PRAGMA busy_timeout=5000",
            "PRAGMA synchronous=NORMAL"
        ]
        for pragma in pragmas:
            self._conn.execute(pragma)
    
    @property
    def row_factory(self):
        """row_factory getter - 70+ 곳 호환성"""
        return self._row_factory
    
    @row_factory.setter
    def row_factory(self, factory):
        """row_factory setter - sqlite3.Row를 dict_row로 자동 매핑"""
        self._row_factory = factory
        
        if self.is_postgres:
            # PostgreSQL은 연결 수준에서 이미 dict_row 설정됨
            if factory == sqlite3.Row:
                pass  # 이미 dict_row로 동작
            elif factory is None:
                pass  # row_factory 해제 처리
        else:
            # SQLite는 그대로 적용
            self._conn.row_factory = factory
    
    def execute(self, sql, params=()):
        """직접 execute 호출 지원 + 자동 SQL 변환"""
        cursor = self.cursor()
        return cursor.execute(sql, params)
    
    def cursor(self):
        """호환 커서 반환"""
        real_cursor = self._conn.cursor()
        return CompatCursor(real_cursor, self)
    
    def _convert_sql(self, sql):
        """안전한 SQL 변환"""
        if not self.is_postgres:
            return sql
        
        # 1. 플레이스홀더 변환 (v7: 문자열 리터럴 보호)
        sql = self._safe_placeholder_conversion(sql)
        
        # 2. 제한적 패턴 변환
        conversions = {
            r"datetime\('now'\)": "CURRENT_TIMESTAMP",
            r"date\('now'\)": "CURRENT_DATE",
            r"datetime\('([^']+)'\)": r"'\1'::TIMESTAMP",  # datetime('2024-01-01') -> '2024-01-01'::TIMESTAMP
            r"BEGIN IMMEDIATE": "START TRANSACTION",
            r"BEGIN EXCLUSIVE": "START TRANSACTION",
            r"\bDATETIME\b": "TIMESTAMP",  # DATETIME -> TIMESTAMP 변환
            r"INTEGER PRIMARY KEY AUTOINCREMENT": "SERIAL PRIMARY KEY",  # AUTOINCREMENT -> SERIAL
            r"INTEGER DEFAULT 1": "INTEGER DEFAULT 1",  # INTEGER boolean값 유지
            r"INTEGER DEFAULT 0": "INTEGER DEFAULT 0",  # INTEGER boolean값 유지
        }
        
        # UPDATE SET 절인지 확인 (SET 절에서는 캐스팅 사용 안 함)
        if 'UPDATE' in sql.upper() and 'SET' in sql.upper():
            # UPDATE 문에서는 boolean 캐스팅을 하지 않음
            pass
        else:
            # WHERE, AND, OR 절에서만 boolean 캐스팅 적용
            boolean_conversions = {
                # WHERE/AND/OR 연산자와 함께 사용되는 경우만 처리
                r"\bWHERE\s+is_active\s*=\s*1\b": "WHERE is_active::int = 1",
                r"\bWHERE\s+is_deleted\s*=\s*0\b": "WHERE is_deleted::int = 0",
                r"\bWHERE\s+is_active\s*=\s*0\b": "WHERE is_active::int = 0",
                r"\bWHERE\s+is_deleted\s*=\s*1\b": "WHERE is_deleted::int = 1",
                r"\bAND\s+is_active\s*=\s*1\b": "AND is_active::int = 1",
                r"\bAND\s+is_deleted\s*=\s*0\b": "AND is_deleted::int = 0",
                r"\bAND\s+is_active\s*=\s*0\b": "AND is_active::int = 0",
                r"\bAND\s+is_deleted\s*=\s*1\b": "AND is_deleted::int = 1",
                r"\bOR\s+is_active\s*=\s*1\b": "OR is_active::int = 1",
                r"\bOR\s+is_deleted\s*=\s*0\b": "OR is_deleted::int = 0",
                r"\bOR\s+is_active\s*=\s*0\b": "OR is_active::int = 0",
                r"\bOR\s+is_deleted\s*=\s*1\b": "OR is_deleted::int = 1",
            }
            conversions.update(boolean_conversions)
        
        for pattern, replacement in conversions.items():
            sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
        
        return sql
    
    def _safe_placeholder_conversion(self, sql):
        """
        문자열 리터럴 내 ? 보호하면서 변환
        SQL 표준: '' (작은따옴표 두개)가 이스케이프
        """
        result = []
        i = 0
        in_string = False
        string_char = None
        
        while i < len(sql):
            char = sql[i]
            
            # 문자열 시작
            if char in ("'", '"') and not in_string:
                in_string = True
                string_char = char
                result.append(char)
                i += 1
            
            # 문자열 종료 체크
            elif char == string_char and in_string:
                # SQL 표준 이스케이프 체크: '' 또는 ""
                if i + 1 < len(sql) and sql[i + 1] == string_char:
                    # 이스케이프된 따옴표 - 문자열 계속
                    result.append(char)
                    result.append(sql[i + 1])
                    i += 2
                else:
                    # 문자열 종료
                    in_string = False
                    string_char = None
                    result.append(char)
                    i += 1
            
            # 플레이스홀더 변환
            elif char == '?' and not in_string:
                result.append('%s')
                i += 1
            
            # 일반 문자
            else:
                result.append(char)
                i += 1
        
        return ''.join(result)
    
    def _convert_params(self, params):
        """파라미터 타입 변환"""
        if params:
            if isinstance(params, (list, tuple)):
                return tuple(self._convert_single_param(p) for p in params)
        return params
    
    def _convert_single_param(self, param):
        """개별 파라미터 변환 (psycopg Json 어댑터 포함)"""
        if self.is_postgres and PSYCOPG_AVAILABLE:
            # PostgreSQL: dict/list를 psycopg Jsonb 어댑터로 변환
            if isinstance(param, (dict, list)):
                return Jsonb(param)
        elif isinstance(param, (dict, list)):
            # SQLite 또는 psycopg 없을 때: JSON 문자열로 변환
            return json.dumps(param, ensure_ascii=False)
        
        return param
    
    def _handle_pragma(self, sql, params):
        """PRAGMA 명령 처리 - table_info 제외"""
        pragma_upper = sql.strip().upper()
        
        if not self.is_postgres:
            # SQLite는 그대로 실행
            return self._conn.execute(sql, params)
        
        # PostgreSQL에서 PRAGMA 처리
        if any(x in pragma_upper for x in ['JOURNAL_MODE', 'BUSY_TIMEOUT', 'SYNCHRONOUS', 'FOREIGN_KEYS']):
            # 이런 PRAGMA들은 PostgreSQL에서 무시 (no-op)
            return EmptyResult()
        else:
            # 기타 PRAGMA
            return EmptyResult()
    
    def commit(self):
        return self._conn.commit()
    
    def rollback(self):
        return self._conn.rollback()
    
    def close(self):
        return self._conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


class CompatCursor:
    """SQLite cursor API 완벽 호환 - v7 수정"""
    
    def __init__(self, real_cursor, conn_wrapper):
        self._cursor = real_cursor
        self._conn = conn_wrapper
        self._lastrowid = None
        self._rowcount = None
        self._pragma_result = None  # PRAGMA 결과 캐시
        self._cached_pragma_result = None  # PRAGMA table_info 캐시
    
    @property
    def lastrowid(self):
        """cursor.lastrowid 에뮬레이션 (9곳 사용)"""
        return self._lastrowid
    
    @property
    def rowcount(self):
        return self._cursor.rowcount if hasattr(self._cursor, 'rowcount') else self._rowcount
    
    def execute(self, sql, params=()):
        """기본 execute - PRAGMA table_info 완벽 처리"""
        
        # SQL 변환
        sql_original = sql
        sql = self._conn._convert_sql(sql)
        params = self._conn._convert_params(params)
        
        # PRAGMA table_info 특별 처리 (v7 필수)
        if 'PRAGMA' in sql_original.upper() and 'TABLE_INFO' in sql_original.upper():
            if self._conn.is_postgres:
                # 테이블명 추출
                match = re.search(r'PRAGMA\s+table_info\s*\(\s*["\']?(\w+)["\']?\s*\)', 
                                 sql_original, re.IGNORECASE)
                if match:
                    table_name = match.group(1)
                    
                    # PostgreSQL에서 SQLite 형태로 변환하는 쿼리 실행
                    pg_sql = """
                        WITH pk_cols AS (
                            SELECT kcu.column_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage kcu 
                                ON tc.constraint_name = kcu.constraint_name
                            WHERE tc.table_name = %s 
                                AND tc.constraint_type = 'PRIMARY KEY'
                        )
                        SELECT 
                            ordinal_position - 1 as cid,
                            c.column_name as name,
                            CASE 
                                WHEN data_type = 'character varying' THEN 'TEXT'
                                WHEN data_type = 'integer' THEN 'INTEGER'
                                WHEN data_type = 'bigint' THEN 'INTEGER'
                                WHEN data_type = 'jsonb' THEN 'TEXT'
                                WHEN data_type = 'timestamp without time zone' THEN 'TIMESTAMP'
                                WHEN data_type = 'boolean' THEN 'INTEGER'  -- v7: BOOLEAN→INTEGER
                                ELSE UPPER(data_type)
                            END as type,
                            CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END as notnull,
                            column_default as dflt_value,
                            CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END as pk
                        FROM information_schema.columns c
                        LEFT JOIN pk_cols pk ON c.column_name = pk.column_name
                        WHERE c.table_name = %s
                        ORDER BY ordinal_position
                    """
                    
                    # 실제 실행
                    self._cursor.execute(pg_sql, (table_name, table_name))
                    
                    # PRAGMA table_info 결과를 즉시 SqliteRowCompat으로 변환
                    rows = self._cursor.fetchall()
                    if rows and isinstance(rows[0], dict):
                        compat_rows = [SqliteRowCompat(row, row.keys()) for row in rows]
                        self._cached_pragma_result = compat_rows
                    else:
                        self._cached_pragma_result = rows
                    
                    return self  # fetchall() 가능하도록
            else:
                # SQLite는 그대로 실행
                self._cursor.execute(sql_original, params)
                return self
        
        # 기타 PRAGMA 처리
        elif sql.strip().upper().startswith('PRAGMA'):
            result = self._conn._handle_pragma(sql, params)
            if isinstance(result, EmptyResult):
                self._pragma_result = result
                return self
        
        # 일반 SQL 실행
        result = self._cursor.execute(sql, params)
        self._rowcount = self._cursor.rowcount if hasattr(self._cursor, 'rowcount') else -1
        
        return self
    
    def execute_with_returning_id(self, sql, params=(), id_column='id'):
        """INSERT 후 ID 반환이 필요한 경우에만 사용 (9곳)"""
        if self._conn.is_postgres:
            # PostgreSQL: RETURNING 추가
            if 'INSERT' in sql.upper() and 'RETURNING' not in sql.upper():
                sql = sql.rstrip(';') + f' RETURNING {id_column}'
            
            sql = self._conn._convert_sql(sql)
            params = self._conn._convert_params(params)
            result = self._cursor.execute(sql, params)
            
            # lastrowid 캐시
            if 'RETURNING' in sql.upper():
                row = self._cursor.fetchone()
                if row:
                    self._lastrowid = row[id_column] if isinstance(row, dict) else row[0]
        else:
            # SQLite: 기존 방식
            sql = self._conn._convert_sql(sql)
            result = self._cursor.execute(sql, params)
            self._lastrowid = self._cursor.lastrowid
        
        return self
    
    def executemany(self, sql, params_list):
        """배치 실행"""
        sql = self._conn._convert_sql(sql)
        
        if self._conn.is_postgres and PSYCOPG_AVAILABLE:
            # PostgreSQL 최적화: psycopg3는 executemany가 자동으로 배치 처리
            try:
                # psycopg3에서는 executemany가 내부적으로 최적화됨
                self._cursor.executemany(sql, params_list)
            except Exception:
                # 안전 폴백: 행 단위 SAVEPOINT로 격리하여 일부 실패에도 전체 트랜잭션 유지
                for params in params_list:
                    try:
                        self._cursor.execute("SAVEPOINT sp_execmany")
                        self._cursor.execute(sql, params)
                        self._cursor.execute("RELEASE SAVEPOINT sp_execmany")
                    except Exception:
                        # 실패한 레코드는 롤백하고 다음으로 진행
                        try:
                            self._cursor.execute("ROLLBACK TO SAVEPOINT sp_execmany")
                        except Exception:
                            pass
        else:
            self._cursor.executemany(sql, params_list)
        
        return self
    
    def fetchone(self):
        """PRAGMA 결과도 처리 + SQLite Row 호환"""
        if self._pragma_result is not None:
            result = self._pragma_result.fetchone()
            self._pragma_result = None
            return result
        
        row = self._cursor.fetchone()
        if row is None:
            return None
        
        # PostgreSQL에서 dict 결과가 나오면 호환 객체로 변환
        if (self._conn.is_postgres and isinstance(row, dict)):
            return SqliteRowCompat(row, row.keys())
        
        return row
    
    def fetchall(self):
        """PRAGMA 결과도 처리 + SQLite Row 호환"""
        if self._pragma_result is not None:
            result = self._pragma_result.fetchall()
            self._pragma_result = None
            return result
        
        # PRAGMA table_info 캐시된 결과 사용
        if self._cached_pragma_result is not None:
            result = self._cached_pragma_result
            self._cached_pragma_result = None
            return result
        
        rows = self._cursor.fetchall()
        
        # PostgreSQL에서 dict 결과들이 나오면 호환 객체로 변환
        if (self._conn.is_postgres and rows and isinstance(rows[0], dict)):
            return [SqliteRowCompat(row, row.keys()) for row in rows]
        
        return rows
    
    def fetchmany(self, size=None):
        """PRAGMA 결과도 처리 + SQLite Row 호환"""
        if self._pragma_result is not None:
            result = self._pragma_result.fetchmany(size)
            self._pragma_result = None
            return result
        
        rows = self._cursor.fetchmany(size)
        
        # PostgreSQL에서 dict 결과들이 나오면 호환 객체로 변환
        if (self._conn.is_postgres and rows and isinstance(rows[0], dict)):
            return [SqliteRowCompat(row, row.keys()) for row in rows]
        
        return rows
    
    def close(self):
        return self._cursor.close()
