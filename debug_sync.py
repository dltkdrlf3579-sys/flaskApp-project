#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
외부 DB 동기화 시 ID 생성 디버깅
"""

import psycopg2
from datetime import datetime

def debug_id_generation():
    """ID 생성 로직 디버깅"""

    print("=" * 60)
    print("ID 생성 로직 디버깅")
    print("=" * 60)

    # 시뮬레이션: 첫 번째 레코드 처리
    idx = 0  # 첫 번째 레코드
    date_str = '241216'

    print(f"\n1. 정상 처리 시:")
    print(f"   idx = {idx}")
    print(f"   date_str = {date_str}")

    # 정상 케이스
    new_counter = 1
    fs_id = f'FS{date_str}{new_counter:04d}'
    fp_id = f'FP{date_str}{new_counter:05d}'

    print(f"   FS ID: {fs_id} (길이: {len(fs_id)})")
    print(f"   FP ID: {fp_id} (길이: {len(fp_id)})")

    print(f"\n2. Exception fallback 시:")
    print(f"   idx = {idx}")
    print(f"   idx + 1 = {idx + 1}")

    # Exception fallback 케이스
    fs_fallback = f'FS{date_str}{idx+1:04d}'
    fp_fallback = f'FP{date_str}{idx+1:05d}'

    print(f"   FS fallback: {fs_fallback} (길이: {len(fs_fallback)})")
    print(f"   FP fallback: {fp_fallback} (길이: {len(fp_fallback)})")

    print(f"\n3. 만약 idx가 크다면:")
    for test_idx in [9, 99, 999, 9999]:
        fs_test = f'FS{date_str}{test_idx+1:04d}'
        fp_test = f'FP{date_str}{test_idx+1:05d}'
        print(f"   idx={test_idx}: FS={fs_test} (길이:{len(fs_test)}), FP={fp_test} (길이:{len(fp_test)})")

    print(f"\n4. 포맷 자릿수 테스트:")
    counter = 1
    print(f"   {counter:04d} -> '{counter:04d}' (4자리)")
    print(f"   {counter:05d} -> '{counter:05d}' (5자리)")
    print(f"   {counter:06d} -> '{counter:06d}' (6자리)")

    counter = 10000
    print(f"   {counter:04d} -> '{counter:04d}' (4자리 오버플로우)")
    print(f"   {counter:05d} -> '{counter:05d}' (5자리)")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    debug_id_generation()