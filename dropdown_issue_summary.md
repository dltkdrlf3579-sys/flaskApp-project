# 드롭다운 표시 문제 요약

## 문제 상황
Flask 포털의 사고 등록 페이지에서 드롭다운(column3 - 처리상태)이 개별 옵션 대신 JSON 배열 전체를 하나의 옵션으로 표시하는 문제

### 증상
- 예상: 드롭다운에 'a', 'b', 'c' 개별 옵션 표시
- 실제: `["a","b","c"]` 전체가 하나의 옵션으로 표시됨
- 역슬래시 이스케이프 문제도 포함: `[\"a\",\"b\",\"c\"]`

## 관련 파일 및 코드

### 1. app.py (라인 709-727)
```python
def get_dropdown_options_for_display(column_key):
    """드롭다운 옵션을 코드-값 매핑 방식으로 가져오기"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        
        # 활성화된 코드 목록 조회
        codes = conn.execute("""
            SELECT option_code, option_value 
            FROM dropdown_option_codes
            WHERE column_key = ? AND is_active = 1
            ORDER BY display_order
        """, (column_key,)).fetchall()
        
        conn.close()
        
        if codes:
            # 코드-값 매핑 방식 반환
            return [{'code': row['option_code'], 'value': row['option_value']} for row in codes]
```

### 2. app.py - accident_register 라우트 (라인 166-200)
```python
@app.route('/accident-register')
def accident_register():
    conn = get_db_connection()
    columns = conn.execute("""
        SELECT column_key, column_name, column_type, 
               is_required, is_active, dropdown_options, 
               display_order, column_width
        FROM accident_column_config 
        WHERE is_active = 1 
        ORDER BY display_order
    """).fetchall()
    
    # 드롭다운 타입 컬럼에 대해 매핑된 옵션 추가
    columns_with_options = []
    for col in columns:
        col_dict = dict(col)
        if col['column_type'] == 'dropdown':
            mapped_options = get_dropdown_options_for_display(col['column_key'])
            if mapped_options:
                col_dict['dropdown_options_mapped'] = mapped_options
                logger.debug(f"Column {col['column_key']} mapped options: {mapped_options}")
```

### 3. templates/accident-register.html (라인 296-310)
```html
{% elif col.column_type == 'dropdown' %}
    <select class="dynamic-input" data-column-key="{{ col.column_key }}">
        <option value="">선택하세요</option>
        {% if col.dropdown_options_mapped %}
            {% for option in col.dropdown_options_mapped %}
                <option value="{{ option.code }}">{{ option.value }}</option>
            {% endfor %}
        {% elif col.dropdown_options %}
            {% set options = col.dropdown_options | from_json %}
            {% for option in options %}
                <option value="{{ option }}">{{ option }}</option>
            {% endfor %}
        {% endif %}
    </select>
```

### 4. 데이터베이스 테이블 구조

#### accident_column_config 테이블
```sql
CREATE TABLE accident_column_config (
    column_key TEXT PRIMARY KEY,
    column_name TEXT NOT NULL,
    column_type TEXT NOT NULL,
    dropdown_options TEXT,  -- JSON 배열로 저장
    ...
);
```

#### dropdown_option_codes 테이블
```sql
CREATE TABLE dropdown_option_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_key TEXT NOT NULL,
    option_code TEXT NOT NULL,
    option_value TEXT NOT NULL,
    display_order INTEGER,
    is_active INTEGER DEFAULT 1,
    ...
);
```

## 현재 데이터 상태

### column3 데이터
- **accident_column_config 테이블**:
  - dropdown_options: `["a", "b", "c"]` (JSON 배열)

- **dropdown_option_codes 테이블**:
  ```
  COLUMN3_001: 'a'
  COLUMN3_002: 'b'  
  COLUMN3_003: 'c'
  ```

## 디버깅 체크리스트

1. **app.py의 get_dropdown_options_for_display 함수**
   - 정상적으로 코드-값 매핑을 반환하는가?
   - 로그에 올바른 값이 출력되는가?

2. **템플릿 렌더링**
   - dropdown_options_mapped가 제대로 전달되는가?
   - Jinja2 템플릿에서 올바르게 순회하는가?

3. **데이터베이스 값**
   - dropdown_option_codes의 option_value가 문자열인가 JSON인가?
   - 이중/삼중 JSON 인코딩이 있는가?

4. **Flask 디버그 로그**
   - mapped_options의 실제 값 확인
   - 템플릿에 전달되는 context 확인

## 테스트 명령어

```bash
# 데이터베이스 상태 확인
python -c "
import sqlite3
conn = sqlite3.connect('portal.db')
cursor = conn.cursor()
codes = cursor.execute('''
    SELECT option_code, option_value 
    FROM dropdown_option_codes 
    WHERE column_key = 'column3' AND is_active = 1
''').fetchall()
for code in codes:
    print(f'{code[0]}: {repr(code[1])}')
"

# Flask 앱 로그 확인 (디버그 모드)
python app.py

# HTML 출력 확인
curl -s http://127.0.0.1:5000/accident-register | grep -A 10 "column3"
```

## 가능한 원인

1. **데이터 인코딩 문제**: option_value가 이미 JSON 배열로 저장됨
2. **템플릿 렌더링 문제**: dropdown_options_mapped가 제대로 처리 안 됨
3. **Flask 라우트 문제**: get_dropdown_options_for_display 함수가 잘못된 형식 반환
4. **캐싱 문제**: 브라우저 또는 Flask가 이전 데이터를 캐싱

## 해결 방법 시도 순서

1. Flask 앱 재시작
2. 브라우저 캐시 클리어 (Ctrl+F5)
3. 데이터베이스 값 재확인 및 정리
4. app.py의 로깅 추가하여 실제 전달되는 값 확인
5. 템플릿의 dropdown_options_mapped 조건 확인