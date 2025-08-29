#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT 권고: json 변수 충돌 찾기
"""
import ast
import sys

# app.py 읽기
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# AST 파싱
tree = ast.parse(content)

# update-safety-instruction와 update-change-request 함수 찾기
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        if node.name in ['update_safety_instruction', 'update_change_request']:
            print(f"\n=== {node.name} 함수 분석 ===")
            print(f"Line {node.lineno}: 함수 시작")
            
            # 함수 내부의 json 관련 찾기
            for child in ast.walk(node):
                # 변수 할당
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and target.id == 'json':
                            print(f"  -> Line {child.lineno}: json = ... 발견!")
                
                # for 루프 변수
                if isinstance(child, ast.For):
                    if isinstance(child.target, ast.Name) and child.target.id == 'json':
                        print(f"  -> Line {child.lineno}: for json in ... 발견!")
                
                # with as 변수
                if isinstance(child, ast.With):
                    for item in child.items:
                        if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                            if item.optional_vars.id == 'json':
                                print(f"  -> Line {child.lineno}: with ... as json 발견!")
                
                # 함수 인자
                for arg in node.args.args:
                    if arg.arg == 'json':
                        print(f"  -> 함수 인자에 json 사용!")
                
                # json 모듈 접근
                if isinstance(child, ast.Attribute):
                    if isinstance(child.value, ast.Name) and child.value.id == 'json':
                        print(f"  -> Line {child.lineno}: json.{child.attr} 사용")
