#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 5: 누락된 설정 생성 및 검증
"""

import os
import configparser
import secrets

def create_config_if_missing():
    """누락된 설정 생성"""
    config = configparser.ConfigParser()

    if os.path.exists('config.ini'):
        config.read('config.ini', encoding='utf-8')
        print("Existing config.ini found, updating...")
    else:
        print("Creating new config.ini...")

    # APPLICATION 섹션
    if not config.has_section('APPLICATION'):
        config.add_section('APPLICATION')
    if not config.has_option('APPLICATION', 'debug'):
        config.set('APPLICATION', 'debug', 'false')
    if not config.has_option('APPLICATION', 'host'):
        config.set('APPLICATION', 'host', '0.0.0.0')
    if not config.has_option('APPLICATION', 'port'):
        config.set('APPLICATION', 'port', '5000')

    # DATABASE 섹션
    if not config.has_section('DATABASE'):
        config.add_section('DATABASE')
    if not config.has_option('DATABASE', 'postgres_dsn'):
        config.set('DATABASE', 'postgres_dsn',
                   'postgresql://postgres:postgres@localhost/portal_db')

    # SECURITY 섹션
    if not config.has_section('SECURITY'):
        config.add_section('SECURITY')
    if not config.has_option('SECURITY', 'secret_key'):
        # 32바이트 랜덤 시크릿 키 생성
        config.set('SECURITY', 'secret_key', secrets.token_hex(32))
        print("Generated new secret key for security")

    # SSO 섹션 (옵션)
    if not config.has_section('SSO'):
        config.add_section('SSO')
    config.set('SSO', 'enabled', 'false')
    config.set('SSO', 'ldap_server', 'ldap://localhost:389')
    config.set('SSO', 'ldap_base_dn', 'dc=company,dc=com')
    config.set('SSO', 'api_url', 'http://localhost:8080/api/users')

    # REDIS 섹션 (캐싱용)
    if not config.has_section('REDIS'):
        config.add_section('REDIS')
    config.set('REDIS', 'host', 'localhost')
    config.set('REDIS', 'port', '6379')
    config.set('REDIS', 'db', '0')
    config.set('REDIS', 'enabled', 'false')  # Redis 없어도 작동하도록

    # 저장
    with open('config.ini', 'w', encoding='utf-8') as f:
        config.write(f)
    print("config.ini saved successfully")

    # 필요한 디렉토리 생성
    directories = ['backups', 'logs', 'uploads', 'reports']
    for dir_name in directories:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"Created directory: {dir_name}")
        else:
            print(f"Directory exists: {dir_name}")

    print("\nConfiguration complete!")
    return config

def verify_config():
    """설정 검증"""
    print("\n" + "=" * 60)
    print("Verifying configuration...")
    print("=" * 60)

    issues = []

    # config.ini 확인
    if not os.path.exists('config.ini'):
        issues.append("config.ini not found")
    else:
        config = configparser.ConfigParser()
        config.read('config.ini', encoding='utf-8')

        # 필수 섹션 확인
        required_sections = ['APPLICATION', 'DATABASE']
        for section in required_sections:
            if not config.has_section(section):
                issues.append(f"Missing required section: {section}")

        # 보안 키 길이 확인
        if config.has_option('SECURITY', 'secret_key'):
            secret_key = config.get('SECURITY', 'secret_key')
            if len(secret_key) < 32:
                issues.append("Secret key is too short (should be at least 32 characters)")

    # 디렉토리 확인
    required_dirs = ['backups', 'logs']
    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            issues.append(f"Missing directory: {dir_name}")

    # 결과 출력
    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("All configuration checks passed!")
        return True

if __name__ == "__main__":
    # 설정 생성
    config = create_config_if_missing()

    # 설정 검증
    if verify_config():
        print("\nConfiguration is ready for use!")
    else:
        print("\nPlease fix the issues above before continuing.")