#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
한국 시간대 설정 모듈
"""

from datetime import datetime
import pytz

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

def get_korean_time():
    """현재 한국 시간 반환"""
    return datetime.now(KST)

def get_korean_time_str(format='%Y-%m-%d %H:%M:%S'):
    """현재 한국 시간을 문자열로 반환"""
    return get_korean_time().strftime(format)

def convert_to_korean_time(dt):
    """UTC 또는 naive datetime을 한국 시간으로 변환"""
    if dt is None:
        return None
    
    # naive datetime인 경우
    if dt.tzinfo is None:
        # UTC로 간주하고 한국 시간으로 변환
        utc_dt = pytz.UTC.localize(dt)
        return utc_dt.astimezone(KST)
    else:
        # timezone aware인 경우 바로 변환
        return dt.astimezone(KST)