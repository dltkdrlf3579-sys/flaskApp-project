#!/usr/bin/env python3
"""
Full Process 페이지 테스트
"""
from flask import Flask
import sys
import os
import traceback

# app.py 임포트
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

def test_full_process():
    """Full Process 페이지 렌더링 테스트"""
    with app.test_client() as client:
        try:
            response = client.get('/full-process')
            if response.status_code == 500:
                print(f"[ERROR] Status: {response.status_code}")
                print(f"[ERROR] Response: {response.data.decode('utf-8')[:500]}")
            else:
                print(f"[OK] Status: {response.status_code}")
        except Exception as e:
            print(f"[ERROR] Exception: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    test_full_process()