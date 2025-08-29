#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AttachmentService 추가 스크립트 (보드 격리 공통 첨부파일 서비스)
"""
import sys
import io

# Windows 콘솔 인코딩 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 원본 스크립트 전체 내용은 backup 이전 버전을 참고하세요.

if __name__ == "__main__":
    print("AttachmentService를 board_services.py에 주입하는 과거 스크립트입니다 (참고용).")
