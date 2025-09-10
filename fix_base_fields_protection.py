#!/usr/bin/env python3
"""
BASE_FIELDS 보호 추가 스크립트
모든 보드에서 created_at이 custom_data에 의해 덮어써지지 않도록 보호
"""

import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fix_app_py():
    """app.py 파일 수정"""
    
    # app.py 읽기
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. partner_accident 함수에서 accident.update(custom_data) 수정
    old_pattern = r"(\s+)# accident_name이 이미 있으면 custom_data의 빈 값으로 덮어쓰지 않음\n" \
                  r"(\s+)if 'accident_name' in custom_data and not custom_data\['accident_name'\]:\n" \
                  r"(\s+)del custom_data\['accident_name'\]\n" \
                  r"(\s+)\n" \
                  r"(\s+)accident\.update\(custom_data\)  # 최상위 레벨에 병합"
    
    new_code = r"\1# accident_name이 이미 있으면 custom_data의 빈 값으로 덮어쓰지 않음\n" \
               r"\2if 'accident_name' in custom_data and not custom_data['accident_name']:\n" \
               r"\3del custom_data['accident_name']\n" \
               r"\4\n" \
               r"\1# 기본 필드를 보호하면서 custom_data 병합\n" \
               r"\1BASE_FIELDS = {'accident_number', 'created_at', 'updated_at', 'is_deleted', 'synced_at', 'no'}\n" \
               r"\1for k, v in custom_data.items():\n" \
               r"\1    if k not in BASE_FIELDS:\n" \
               r"\1        accident[k] = v"
    
    content = re.sub(old_pattern, new_code, content)
    
    # 백업 생성
    import shutil
    from datetime import datetime
    backup_name = f"app.py.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy('app.py', backup_name)
    logging.info(f"백업 생성: {backup_name}")
    
    # 파일 저장
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    logging.info("✅ app.py 수정 완료")

def fix_add_page_routes():
    """add_page_routes.py 파일 수정"""
    
    try:
        # add_page_routes.py 읽기
        with open('add_page_routes.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # follow_sop_route에서 custom_data 병합 부분 찾기
        if 'followsop.update(custom_data)' in content:
            old_pattern = r"followsop\.update\(custom_data\)"
            new_code = """# 기본 필드를 보호하면서 custom_data 병합
                BASE_FIELDS = {'work_req_no', 'created_at', 'updated_at', 'is_deleted', 'synced_at', 'no'}
                for k, v in custom_data.items():
                    if k not in BASE_FIELDS:
                        followsop[k] = v"""
            
            content = re.sub(old_pattern, new_code, content)
            logging.info("✅ follow_sop_route 수정")
        
        # full_process_route에서 custom_data 병합 부분 찾기
        if 'process.update(custom_data)' in content:
            old_pattern = r"process\.update\(custom_data\)"
            new_code = """# 기본 필드를 보호하면서 custom_data 병합
                BASE_FIELDS = {'fullprocess_number', 'created_at', 'updated_at', 'is_deleted', 'synced_at', 'no'}
                for k, v in custom_data.items():
                    if k not in BASE_FIELDS:
                        process[k] = v"""
            
            content = re.sub(old_pattern, new_code, content)
            logging.info("✅ full_process_route 수정")
        
        # change_request_route에서 custom_data 병합 부분 찾기
        if 'request_item.update(custom_data)' in content:
            old_pattern = r"request_item\.update\(custom_data\)"
            new_code = """# 기본 필드를 보호하면서 custom_data 병합
                BASE_FIELDS = {'change_number', 'created_at', 'updated_at', 'is_deleted', 'synced_at', 'no'}
                for k, v in custom_data.items():
                    if k not in BASE_FIELDS:
                        request_item[k] = v"""
            
            content = re.sub(old_pattern, new_code, content)
            logging.info("✅ change_request_route 수정")
        
        # 백업 생성
        import shutil
        from datetime import datetime
        backup_name = f"add_page_routes.py.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy('add_page_routes.py', backup_name)
        logging.info(f"백업 생성: {backup_name}")
        
        # 파일 저장
        with open('add_page_routes.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        logging.info("✅ add_page_routes.py 수정 완료")
        
    except FileNotFoundError:
        logging.warning("add_page_routes.py 파일을 찾을 수 없습니다.")
    except Exception as e:
        logging.error(f"add_page_routes.py 수정 중 오류: {e}")

def main():
    """메인 실행 함수"""
    logging.info("=" * 50)
    logging.info("BASE_FIELDS 보호 추가 시작")
    
    # app.py 수정
    logging.info("=" * 50)
    logging.info("1. app.py 수정")
    fix_app_py()
    
    # add_page_routes.py 수정
    logging.info("=" * 50)
    logging.info("2. add_page_routes.py 수정")
    fix_add_page_routes()
    
    logging.info("=" * 50)
    logging.info("✅ 모든 수정 완료!")
    logging.info("테스트를 진행해주세요.")

if __name__ == "__main__":
    main()