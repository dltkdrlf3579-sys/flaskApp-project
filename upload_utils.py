"""
파일 업로드 유틸리티 - config.ini 설정에 따른 제한 적용
"""
import os
import re
import time
import unicodedata
import configparser

DEFAULT_FILENAME_FALLBACK = "file"
SAFE_FILENAME_PATTERN = re.compile(r"[^0-9A-Za-z가-힣._-]+")


def sanitize_filename(filename: str, fallback_prefix: str = DEFAULT_FILENAME_FALLBACK) -> str:
    """한글을 포함한 안전한 파일명으로 정규화"""
    if not filename:
        return f"{fallback_prefix}_{int(time.time())}"

    # FileStorage filename may be latin-1 decoded bytes; try to recover UTF-8
    if isinstance(filename, bytes):
        try:
            filename = filename.decode('utf-8')
        except UnicodeDecodeError:
            filename = filename.decode('latin-1', 'ignore')
    else:
        # If the string is made of 8-bit characters only, it may be latin-1 decoded bytes
        try:
            raw_bytes = filename.encode('latin-1')
        except UnicodeEncodeError:
            raw_bytes = None  # contains true Unicode already

        if raw_bytes is not None:
            try:
                decoded = raw_bytes.decode('utf-8')
            except UnicodeDecodeError:
                decoded = None
            if decoded:
                filename = decoded

    # Normalize unicode to prevent equivalent composed forms from being different
    normalized = unicodedata.normalize('NFKC', filename)

    # Replace path separators just in case
    cleaned = normalized.replace('\\', '_').replace('/', '_')

    # Remove any disallowed characters while keeping Korean, digits, ascii, dot, dash, underscore
    cleaned = SAFE_FILENAME_PATTERN.sub('_', cleaned)

    # Trim leading/trailing dots/underscores to avoid hidden files or empty names
    cleaned = cleaned.strip('._ ')

    if not cleaned:
        cleaned = f"{fallback_prefix}_{int(time.time())}"

    return cleaned

class UploadValidator:
    """파일 업로드 검증 클래스"""

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding='utf-8')
        self._load_settings()

    def _load_settings(self):
        """config.ini에서 업로드 설정 로드"""
        # SECURITY 섹션에서 설정 가져오기
        self.max_upload_size_mb = self.config.getint('SECURITY', 'max_upload_size_mb', fallback=10)
        self.max_upload_size_bytes = self.max_upload_size_mb * 1024 * 1024  # MB를 bytes로 변환

        # 허용된 확장자 목록 파싱
        allowed_ext_str = self.config.get('SECURITY', 'allowed_extensions',
                                          fallback='pdf,doc,docx,xls,xlsx,png,jpg,jpeg')
        self.allowed_extensions = set(ext.strip().lower() for ext in allowed_ext_str.split(','))

        print(f"[업로드 설정] 최대 크기: {self.max_upload_size_mb}MB, 허용 확장자: {self.allowed_extensions}")

    def allowed_file(self, filename):
        """
        파일 확장자가 허용된 것인지 확인

        Args:
            filename: 검사할 파일명

        Returns:
            bool: 허용된 확장자면 True, 아니면 False
        """
        if '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in self.allowed_extensions

    def validate_file_size(self, file):
        """
        파일 크기가 제한 내에 있는지 확인

        Args:
            file: werkzeug FileStorage 객체

        Returns:
            tuple: (valid: bool, size_mb: float, error_msg: str or None)
        """
        # 파일 크기 확인
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # 파일 포인터를 다시 처음으로

        size_mb = file_size / (1024 * 1024)

        if file_size > self.max_upload_size_bytes:
            error_msg = f"파일 크기가 제한({self.max_upload_size_mb}MB)을 초과합니다. 현재 크기: {size_mb:.2f}MB"
            return False, size_mb, error_msg

        return True, size_mb, None

    def validate_file(self, file):
        """
        파일의 확장자와 크기를 모두 검증

        Args:
            file: werkzeug FileStorage 객체

        Returns:
            dict: {
                'valid': bool,
                'filename': str (안전한 파일명),
                'extension': str,
                'size_mb': float,
                'errors': list of error messages
            }
        """
        result = {
            'valid': True,
            'filename': None,
            'extension': None,
            'size_mb': 0,
            'errors': []
        }

        # 파일이 없거나 파일명이 없는 경우
        if not file or not file.filename:
            result['valid'] = False
            result['errors'].append("파일이 선택되지 않았습니다")
            return result

        # 안전한 파일명 생성
        result['filename'] = sanitize_filename(file.filename)

        # 확장자 확인
        if '.' in file.filename:
            result['extension'] = file.filename.rsplit('.', 1)[1].lower()

        # 확장자 검증
        if not self.allowed_file(file.filename):
            result['valid'] = False
            result['errors'].append(
                f"허용되지 않은 파일 형식입니다. 허용된 확장자: {', '.join(sorted(self.allowed_extensions))}"
            )

        # 크기 검증
        size_valid, size_mb, size_error = self.validate_file_size(file)
        result['size_mb'] = size_mb

        if not size_valid:
            result['valid'] = False
            result['errors'].append(size_error)

        return result

    def validate_multiple_files(self, files):
        """
        여러 파일을 한번에 검증

        Args:
            files: FileStorage 객체 리스트

        Returns:
            dict: {
                'all_valid': bool,
                'total_size_mb': float,
                'file_results': list of individual validation results,
                'summary_errors': list of summary error messages
            }
        """
        results = {
            'all_valid': True,
            'total_size_mb': 0,
            'file_results': [],
            'summary_errors': []
        }

        for i, file in enumerate(files):
            file_result = self.validate_file(file)
            file_result['index'] = i
            results['file_results'].append(file_result)

            if not file_result['valid']:
                results['all_valid'] = False

            results['total_size_mb'] += file_result['size_mb']

        # 전체 크기 체크 (선택사항 - 필요시 활성화)
        # total_limit_mb = self.max_upload_size_mb * 5  # 예: 개별 제한의 5배
        # if results['total_size_mb'] > total_limit_mb:
        #     results['all_valid'] = False
        #     results['summary_errors'].append(
        #         f"전체 파일 크기가 제한({total_limit_mb}MB)을 초과합니다. "
        #         f"현재 전체 크기: {results['total_size_mb']:.2f}MB"
        #     )

        return results

    def get_allowed_extensions_for_display(self):
        """UI에 표시할 허용 확장자 목록 반환"""
        return ', '.join(sorted(self.allowed_extensions))

    def get_max_size_for_display(self):
        """UI에 표시할 최대 크기 반환"""
        return f"{self.max_upload_size_mb}MB"


# 싱글톤 인스턴스
_upload_validator = None

def get_upload_validator():
    """업로드 검증기 싱글톤 인스턴스 반환"""
    global _upload_validator
    if _upload_validator is None:
        _upload_validator = UploadValidator()
    return _upload_validator


def reload_upload_settings():
    """설정 변경 시 업로드 검증기 재로드"""
    global _upload_validator
    _upload_validator = UploadValidator()
    return _upload_validator


def validate_uploaded_files(files):
    """업로드된 파일 리스트를 검증하고 결과를 반환"""

    validator = get_upload_validator()
    valid_files = []
    errors = []

    for idx, file in enumerate(files):
        if not file or not getattr(file, 'filename', ''):
            continue

        result = validator.validate_file(file)
        safe_name = result.get('filename') or sanitize_filename(file.filename)

        if not result.get('valid', False):
            filename = file.filename or safe_name
            for err in result.get('errors', []):
                errors.append(f"{filename}: {err}")
            continue

        valid_files.append({
            'file': file,
            'safe_filename': safe_name,
            'extension': result.get('extension'),
            'size_mb': result.get('size_mb', 0),
            'index': idx
        })

    return valid_files, errors
