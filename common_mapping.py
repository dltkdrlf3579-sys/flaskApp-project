"""
공통 매핑 모듈
모든 게시판에서 코드값을 라벨로 변환하는 공통 함수
"""
import json
import logging
from board_services import CodeService

def smart_apply_mappings(data_list, board_type, dynamic_columns, db_path):
    """
    데이터를 분석해서 매핑 가능한 필드 자동 감지 및 적용
    
    Args:
        data_list: 매핑할 데이터 리스트
        board_type: 게시판 타입 (accident, safety_instruction, change_request 등)
        dynamic_columns: 동적 컬럼 설정
        db_path: 데이터베이스 경로
    
    Returns:
        매핑이 적용된 데이터 리스트
    """
    if not data_list:
        return data_list
    
    try:
        code_service = CodeService(board_type, db_path)
    except Exception as e:
        logging.error(f"CodeService 초기화 실패: {e}")
        return data_list
    
    # 캐싱으로 성능 개선
    if not hasattr(smart_apply_mappings, 'cache'):
        smart_apply_mappings.cache = {}
    
    cache_key = board_type
    
    # 캐시에 없으면 매핑 정보 생성
    if cache_key not in smart_apply_mappings.cache:
        # 첫 번째 데이터의 키를 기준으로 분석 (안전한 처리)
        if data_list:
            first_item = data_list[0]
            if hasattr(first_item, 'keys'):
                sample_keys = first_item.keys()
            elif isinstance(first_item, dict):
                sample_keys = first_item.keys()
            else:
                # 객체의 속성을 키로 사용
                sample_keys = [attr for attr in dir(first_item) if not attr.startswith('_')]
        else:
            sample_keys = []
        
        # 제외할 시스템 필드들
        exclude_fields = {
            'id', 'no', 'created_at', 'updated_at', 'custom_data', 
            'is_deleted', 'synced_at', 'detailed_content', 'accident_number',
            'request_number', 'issue_number', 'business_number', 'custom_mapped',
            'accident_name', 'company_name', 'requester_name', 'requester_department',
            'change_reason', 'current_value', 'new_value', 'violation_content',
            'accident_content', 'accident_date', 'report_date', 'violation_date',
            'discipline_date', 'access_ban_start_date', 'access_ban_end_date',
            'period', 'penalty_points', 'disciplined_person_id', 'issuer',
            'issuer_department', 'primary_company', 'primary_business_number',
            'subcontractor', 'subcontractor_business_number', 'disciplined_person',
            'gbm', 'business_division', 'team', 'department', 'day_of_week',
            'location_detail', 'floor', 'building_name'
        }
        
        # 매핑 가능한 필드와 매핑 동시에 저장
        field_mappings = {}
        for key in sample_keys:
            # 이미 _label이 붙은 필드는 건너뛰기
            if key.endswith('_label'):
                continue
                
            # 시스템 필드나 텍스트 필드는 제외
            if key not in exclude_fields:
                try:
                    codes = code_service.list(key)
                    if codes and len(codes) > 0:
                        field_mappings[key] = {c['option_code']: c['option_value'] for c in codes}
                        logging.info(f"[{board_type}] {key} 필드 매핑 생성: {len(codes)}개 옵션")
                except Exception as e:
                    logging.debug(f"[{board_type}] {key} 필드 매핑 조회 실패: {e}")
        
        smart_apply_mappings.cache[cache_key] = field_mappings
        logging.info(f"[{board_type}] 총 {len(field_mappings)}개 필드 매핑 캐시 저장")
    else:
        field_mappings = smart_apply_mappings.cache[cache_key]
    
    # 데이터에 매핑 적용
    for item in data_list:
        # 1. 기본 필드 매핑
        for field, mapping in field_mappings.items():
            field_value = item.get(field)
            if field_value:
                mapped_value = mapping.get(field_value, field_value)
                item[f'{field}_label'] = mapped_value
            else:
                item[f'{field}_label'] = '-'
        
        # 2. 동적 컬럼 매핑 처리
        # custom_data가 이미 플래튼되어 있으므로, 동적 컬럼의 값은 item 최상위에 있음
        custom_mapped = {}
        
        if dynamic_columns:
            # 각 동적 컬럼에 대해 처리
            for col in dynamic_columns:
                key = col.get('column_key')
                if not key:
                    continue
                
                # 값은 이미 플래튼되어 item 최상위에 있음
                value = item.get(key, '')
                
                # 드롭다운 타입이고 값이 있으면 매핑 시도
                if value and col.get('column_type') == 'dropdown':
                    try:
                        # 동적 컬럼용 코드 조회
                        col_codes = code_service.list(key)
                        if col_codes:
                            col_mapping = {c['option_code']: c['option_value'] for c in col_codes}
                            custom_mapped[key] = col_mapping.get(value, value)
                        else:
                            custom_mapped[key] = value
                    except Exception as e:
                        logging.debug(f"동적 컬럼 {key} 매핑 실패: {e}")
                        custom_mapped[key] = value
                else:
                    # 드롭다운이 아니거나 값이 없으면 그대로
                    custom_mapped[key] = value if value else '-'
        
        # 매핑된 custom_data 저장
        item['custom_mapped'] = custom_mapped
    
    return data_list