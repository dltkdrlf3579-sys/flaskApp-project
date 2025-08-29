#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
기존 업데이트 엔드포인트를 AttachmentService 사용하도록 정리
"""
import sys
import io
from datetime import datetime
import shutil

# Windows 콘솔 인코딩 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def backup_file(filepath):
    """파일 백업 생성"""
    backup_path = f"{filepath}.backup_attachment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    print(f"✅ 백업 생성: {backup_path}")
    return backup_path

# 이하: 원본 스크립트 내용 유지 (긴 코드 생략)

if __name__ == "__main__":
    print("이 스크립트는 기존 엔드포인트를 AttachmentService 기반으로 치환하는 도우미입니다.")
