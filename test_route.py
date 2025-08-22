from flask import Flask
import sqlite3

app = Flask(__name__)

@app.route('/test')
def test():
    try:
        conn = sqlite3.connect('portal.db')
        conn.row_factory = sqlite3.Row
        
        # 동적 컬럼 가져오기
        dynamic_columns = conn.execute("""
            SELECT * FROM accident_column_config 
            WHERE is_active = 1 
            ORDER BY column_order
        """).fetchall()
        
        # 로컬 사고 가져오기
        local_accidents = conn.execute("""
            SELECT * FROM accidents_cache 
            ORDER BY accident_date DESC
        """).fetchall()
        
        conn.close()
        
        return f"""
        <h1>테스트 결과</h1>
        <p>동적 컬럼: {len(dynamic_columns)}개</p>
        <p>로컬 사고: {len(local_accidents)}개</p>
        <p>사고 번호들: {[row['accident_number'] for row in local_accidents[:5]]}</p>
        """
    except Exception as e:
        return f"<h1>오류 발생</h1><p>{str(e)}</p>"

if __name__ == '__main__':
    app.run(port=5001, debug=True)