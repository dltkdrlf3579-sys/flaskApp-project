#!/usr/bin/env python3
"""
pragma_table_info를 PostgreSQL information_schema로 대체
"""
import os
import glob

def fix_pragma_in_file(filepath):
    """파일에서 pragma_table_info를 information_schema로 변경"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # pragma_table_info를 PostgreSQL 호환 쿼리로 변경
    if 'pragma_table_info' in content:
        # Pattern 1: SELECT COUNT(*) FROM pragma_table_info('table_name') WHERE name='column'
        import re
        pattern1 = r"SELECT COUNT\(\*\) FROM pragma_table_info\('([^']+)'\)\s+WHERE name='([^']+)'"
        replacement1 = r"""SELECT COUNT(*) FROM information_schema.columns 
            WHERE table_name='\1' AND column_name='\2'"""
        content = re.sub(pattern1, replacement1, content)
        
        # Pattern 2: 변수를 사용하는 경우
        pattern2 = r'SELECT COUNT\(\*\) FROM pragma_table_info\(\{([^}]+)\}\)\s+WHERE name=\'([^\']+)\''
        replacement2 = r"""SELECT COUNT(*) FROM information_schema.columns 
            WHERE table_name={{\1}} AND column_name='\2'"""
        content = re.sub(pattern2, replacement2, content)
        
        # f-string 패턴
        pattern3 = r'f"""[\s\S]*?SELECT COUNT\(\*\) FROM pragma_table_info\(\'\{self\.([^}]+)\}\'\)[\s\S]*?WHERE name=\'([^\']+)\'[\s\S]*?"""'
        def replace_fstring(match):
            table_var = match.group(1)
            column = match.group(2)
            return f'''f"""
            SELECT COUNT(*) FROM information_schema.columns 
            WHERE table_name='{{self.{table_var}}}' AND column_name='{column}'
        """'''
        content = re.sub(pattern3, replace_fstring, content, flags=re.MULTILINE)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 수정됨: {filepath}")
        return True
    return False

def main():
    """모든 Python 파일에서 pragma_table_info 수정"""
    fixed_count = 0
    
    # column_service.py 직접 수정
    if os.path.exists('column_service.py'):
        if fix_pragma_in_file('column_service.py'):
            fixed_count += 1
    
    # 다른 파일들도 확인
    for filepath in glob.glob('*.py'):
        if filepath != 'fix_pragma_error.py':
            with open(filepath, 'r', encoding='utf-8') as f:
                if 'pragma_table_info' in f.read():
                    if fix_pragma_in_file(filepath):
                        fixed_count += 1
    
    print(f"\n총 {fixed_count}개 파일 수정됨")

if __name__ == "__main__":
    main()