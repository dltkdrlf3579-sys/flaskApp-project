"""
PostgreSQL 간단 콘솔
사용법: python pg_console.py
"""
import psycopg

print("PostgreSQL 간단 콘솔")
print("종료: exit 또는 quit")
print("-" * 50)

conn = psycopg.connect('postgresql://postgres:admin123@localhost:5432/portal_dev')
cursor = conn.cursor()

while True:
    query = input("\nSQL> ").strip()
    
    if query.lower() in ['exit', 'quit']:
        break
    
    if not query:
        continue
    
    try:
        cursor.execute(query)
        
        if query.upper().startswith('SELECT'):
            rows = cursor.fetchall()
            if rows:
                # 컬럼명 출력
                columns = [desc[0] for desc in cursor.description]
                print(" | ".join(columns))
                print("-" * 80)
                
                # 데이터 출력 (최대 10행)
                for i, row in enumerate(rows[:10]):
                    print(" | ".join(str(val)[:30] for val in row))
                
                if len(rows) > 10:
                    print(f"... {len(rows)-10} more rows")
            else:
                print("No results")
        else:
            conn.commit()
            print(f"Query executed successfully")
            
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()

cursor.close()
conn.close()
print("\nGoodbye!")