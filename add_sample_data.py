#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os

def add_sample_partners():
    """샘플 협력사 데이터 추가"""
    
    db_path = 'portal.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("샘플 협력사 데이터를 추가합니다...")
    
    # 기존 데이터 삭제
    cursor.execute("DELETE FROM partners_cache")
    
    # 샘플 데이터 (사업자번호는 하이픈 없는 10자리)
    sample_partners = [
        ('1234567890', '삼성전자', '이재용', 100000, 'IT서비스', 'IT', '소프트웨어', '1969-01-13', 119400000000000, 279650000000000, '반도체, 스마트폰', 'ISO9001,ISO14001', 'A+', '김철수', '02-2255-0114', 'contact@samsung.com'),
        ('2345678901', 'LG전자', '조성진', 75000, 'IT서비스', 'IT', '전자제품', '1958-10-01', 3636110000000, 63264000000000, '가전제품, 스마트폰', 'ISO9001', 'A', '박영희', '02-3777-1114', 'info@lge.com'),
        ('3456789012', '현대자동차', '장재훈', 120000, '제조업', '자동차', '완성차', '1967-12-29', 25800000000000, 142838000000000, '승용차, 상용차', 'TS16949,ISO14001', 'A+', '이민수', '02-3464-1114', 'global@hyundai.com'),
        ('4567890123', 'SK하이닉스', '곽노정', 35000, 'IT서비스', 'IT', '반도체', '1983-11-15', 3507570000000, 41408000000000, 'DRAM, NAND', 'ISO9001,OHSAS18001', 'A', '정미경', '031-5185-4114', 'pr@skhynix.com'),
        ('5678901234', '포스코', '정준영', 19000, '제조업', '철강', '제철', '1968-04-01', 17800000000000, 73071000000000, '철강재, 스테인리스', 'ISO9001,ISO14001', 'A+', '김영수', '054-220-0114', 'webmaster@posco.com'),
        ('6789012345', '네이버', '최수연', 12000, 'IT서비스', 'IT', '인터넷서비스', '1999-06-02', 164000000000, 5626000000000, '검색엔진, 웹서비스', 'ISO27001', 'A', '박소영', '1588-3820', 'dl_naverhelp@navercorp.com'),
        ('7890123456', '카카오', '홍은택', 8500, 'IT서비스', 'IT', '인터넷서비스', '1995-02-16', 52700000000, 4227000000000, '메신저, 게임', 'ISO27001', 'A', '이지은', '02-6712-4114', 'service@kakaocorp.com'),
        ('8901234567', '셀트리온', '서정진', 5500, '제약업', '바이오', '의약품', '2002-01-01', 13000000000, 2500000000000, '바이오의약품', 'GMP,ISO13485', 'A', '조현정', '032-850-5500', 'webmaster@celltrion.com'),
        ('9012345678', '한화시스템', '김연철', 4500, '제조업', '방산', '시스템', '1978-12-01', 400000000000, 3200000000000, '방산시스템, 항공우주', 'AS9100,ISO14001', 'B+', '김태현', '02-729-1114', 'webmaster@hanwhasystems.com'),
        ('0123456789', '두산에너빌리티', '박상현', 9000, '제조업', '기계', '발전설비', '1962-05-01', 1700000000000, 15200000000000, '발전설비, 담수화', 'ISO9001,ASME', 'A', '송미라', '051-462-1114', 'webmaster@doosanenerbility.com')
    ]
    
    # 데이터 삽입
    for partner in sample_partners:
        cursor.execute('''
            INSERT INTO partners_cache (
                business_number, company_name, representative, regular_workers,
                business_type, business_type_major, business_type_minor, establishment_date,
                capital_amount, annual_revenue, main_products, certification, safety_rating,
                contact_person, phone_number, email
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', partner)
    
    conn.commit()
    
    # 확인
    cursor.execute("SELECT COUNT(*) FROM partners_cache")
    count = cursor.fetchone()[0]
    print(f"{count}개의 협력사 데이터가 추가되었습니다.")
    
    # 몇 개 예시 출력
    cursor.execute("SELECT business_number, company_name FROM partners_cache LIMIT 3")
    samples = cursor.fetchall()
    print("\n추가된 데이터 예시:")
    for biz_no, name in samples:
        print(f"   - {biz_no}: {name}")
    
    conn.close()
    return True

if __name__ == "__main__":
    print("Flask Portal 샘플 데이터 추가 스크립트")
    print("=" * 50)
    
    if add_sample_partners():
        print("\n모든 샘플 데이터가 성공적으로 추가되었습니다!")
        print("이제 Flask 애플리케이션을 실행하고 브라우저에서 확인하세요.")
        print("   python app.py")
    else:
        print("\n데이터 추가 중 오류가 발생했습니다.")