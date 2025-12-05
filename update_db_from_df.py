#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
변환된 DataFrame을 다시 DB로 업데이트
"""

import json
from sqlalchemy import create_engine, text

def update_custom_data_to_db(df, engine, table_name='full_process', key_column='fullprocess_number'):
    """
    DataFrame의 custom_data를 DB로 업데이트

    Parameters:
    - df: 변환된 DataFrame
    - engine: SQLAlchemy engine
    - table_name: 테이블명 (default: 'full_process')
    - key_column: Primary key 컬럼명 (default: 'fullprocess_number')
    """

    with engine.connect() as conn:
        for idx, row in df.iterrows():
            # custom_data를 JSON 문자열로 변환
            custom_data_json = json.dumps(row['custom_data'], ensure_ascii=False)

            # UPDATE 쿼리 실행
            query = text(f"""
                UPDATE {table_name}
                SET custom_data = :custom_data
                WHERE {key_column} = :key_value
            """)

            conn.execute(query, {
                'custom_data': custom_data_json,
                'key_value': row[key_column]
            })

            print(f"Updated {row[key_column]}")

        conn.commit()
        print(f"✓ Updated {len(df)} records")


# 사용 예시
if __name__ == "__main__":
    from sqlalchemy import create_engine
    import pandas as pd
    from transform_df_fixed import transform_custom_data_from_df

    # 1. DB 연결
    engine = create_engine('postgresql://postgres:admin123@localhost:5432/portal_dev')

    # 2. 데이터 읽기
    query = "SELECT fullprocess_number, custom_data FROM full_process WHERE custom_data IS NOT NULL LIMIT 3"
    df = pd.read_sql(query, engine)

    # 3. 변환
    df = transform_custom_data_from_df(df)

    # 4. DB 업데이트
    update_custom_data_to_db(df, engine)