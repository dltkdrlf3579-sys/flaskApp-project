# Flask 드롭다운 표시 문제 - GPT 상담용

## 🔴 문제 상황
Flask 애플리케이션의 드롭다운 메뉴가 개별 옵션 대신 JSON 배열 전체를 하나의 옵션으로 표시하는 문제

### 현재 증상
- **예상 동작**: 드롭다운에 개별 옵션들이 표시되어야 함
  - 옵션 1: a
  - 옵션 2: b  
  - 옵션 3: c

- **실제 동작**: JSON 배열이 하나의 옵션으로 표시됨
  - 옵션 1: `["a","b","c"]` (전체가 하나로)

### 스크린샷 설명
- 코드 컬럼에 `COLUMN3_001`이 표시됨
- 표시값 컬럼에 `["["a","b","w","e"]"]` 같은 중첩된 JSON이 표시됨
- 드롭다운 선택 시 배열 전체가 하나의 선택지로 나타남

## 📁 관련 파일 및 코드

### 1. **app.py** (메인 Flask 애플리케이션)
```python
# 라인 709-727: 드롭다운 옵션 가져오는 함수
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
            return [{'code': row['option_code'], 'value': row['option_value']} 
                    for row in codes]
        else:
            return None
    except Exception as e:
        logger.error(f"드롭다운 옵션 조회 오류: {e}")
        return None

# 라인 166-200: accident_register 라우트
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
        columns_with_options.append(col_dict)
    
    return render_template('accident-register.html', 
                          columns=columns_with_options)
```

### 2. **templates/accident-register.html** (프론트엔드 템플릿)
```html
<!-- 라인 296-310: 드롭다운 렌더링 부분 -->
{% elif col.column_type == 'dropdown' %}
    <select class="dynamic-input" data-column-key="{{ col.column_key }}">
        <option value="">선택하세요</option>
        {% if col.dropdown_options_mapped %}
            <!-- 코드-값 매핑 방식 -->
            {% for option in col.dropdown_options_mapped %}
                <option value="{{ option.code }}">{{ option.value }}</option>
            {% endfor %}
        {% elif col.dropdown_options %}
            <!-- 기존 JSON 방식 (폴백) -->
            {% set options = col.dropdown_options | from_json %}
            {% for option in options %}
                <option value="{{ option }}">{{ option }}</option>
            {% endfor %}
        {% endif %}
    </select>
{% endif %}
```

### 3. **데이터베이스 스키마**

#### accident_column_config 테이블
```sql
CREATE TABLE accident_column_config (
    column_key TEXT PRIMARY KEY,
    column_name TEXT NOT NULL,
    column_type TEXT NOT NULL,  -- 'dropdown', 'text', 'date' 등
    dropdown_options TEXT,       -- JSON 배열 (레거시)
    is_required INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    display_order INTEGER,
    column_width INTEGER
);
```

#### dropdown_option_codes 테이블 (새로 추가된 테이블)
```sql
CREATE TABLE dropdown_option_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_key TEXT NOT NULL,      -- 'column3' 등
    option_code TEXT NOT NULL,     -- 'COLUMN3_001' 등
    option_value TEXT NOT NULL,    -- 표시될 값 ('a', 'b', 'c' 등)
    display_order INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔍 디버깅 정보

### 현재 데이터베이스 상태 확인 스크립트
```python
import sqlite3
import json

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

# column3의 dropdown_option_codes 확인
print("=== dropdown_option_codes 테이블 ===")
codes = cursor.execute("""
    SELECT option_code, option_value 
    FROM dropdown_option_codes 
    WHERE column_key = 'column3' AND is_active = 1
    ORDER BY display_order
""").fetchall()

for code in codes:
    print(f"Code: {code[0]}")
    print(f"Value (raw): {repr(code[1])}")
    print(f"Value type: {type(code[1])}")
    # JSON 파싱 시도
    try:
        parsed = json.loads(code[1])
        print(f"Parsed as JSON: {parsed}")
    except:
        print("Not JSON, plain string")
    print("---")

conn.close()
```

### 함수 테스트 스크립트
```python
from app import get_dropdown_options_for_display

result = get_dropdown_options_for_display('column3')
print(f"Function returns: {result}")
for item in result:
    print(f"  Code: {item['code']}, Value: {repr(item['value'])}")
```

## 🐛 의심되는 문제점들

1. **데이터 저장 문제**
   - `option_value`가 개별 문자열이 아닌 JSON 배열로 저장됨
   - 예: 'a' 대신 '["a","b","c"]'가 저장됨

2. **이중/삼중 JSON 인코딩**
   - 데이터가 여러 번 JSON 인코딩되어 저장됨
   - 예: `["[\"a\",\"b\",\"c\"]"]`

3. **코드 에디터 저장 로직 문제**
   - `admin-accident-columns-simplified.html`에서 저장 시 잘못된 형식으로 저장

4. **템플릿 렌더링 문제**
   - `dropdown_options_mapped`가 제대로 파싱되지 않음

## 💡 시도해본 해결책들

1. ✅ 데이터베이스 값 직접 수정
   - `DELETE FROM dropdown_option_codes WHERE column_key = 'column3'`
   - 올바른 개별 값으로 재삽입
   - **결과**: 일시적으로 해결되나, 코드 에디터로 수정 시 다시 문제 발생

2. ❌ Flask 앱 재시작
   - **결과**: 효과 없음

3. ❌ 브라우저 캐시 클리어
   - **결과**: 효과 없음

## 🎯 핵심 질문

1. `dropdown_option_codes.option_value`에 저장될 때 왜 JSON 배열로 저장되는가?
2. 코드 에디터(`admin-accident-columns-simplified.html`)에서 저장하는 로직이 잘못되었는가?
3. `get_dropdown_options_for_display` 함수가 올바르게 데이터를 가져오는데도 템플릿에서 잘못 표시되는 이유는?

## 📝 추가 필요 정보

- Flask 버전: Flask 2.3.2
- Python 버전: 3.13
- SQLite3 사용
- Jinja2 템플릿 엔진

## 🆘 도움 요청

위 상황에서 드롭다운이 개별 옵션으로 표시되지 않고 JSON 배열 전체가 하나의 옵션으로 표시되는 문제를 해결하려면 어떻게 해야 할까요? 특히 코드 에디터에서 저장할 때 올바른 형식으로 저장되도록 하는 방법이 필요합니다.