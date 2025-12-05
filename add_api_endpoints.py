# Follow SOP API 엔드포인트
@app.route("/api/follow-sop-columns", methods=["GET"])
def get_follow_sop_columns():
    """Follow SOP 페이지 동적 컬럼 설정 조회"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        columns = column_service.list_columns()
        return jsonify(columns)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-columns", methods=["POST"])
def add_follow_sop_column():
    """Follow SOP 페이지 동적 컬럼 추가"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        result = column_service.add_column(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-columns/<int:column_id>", methods=["PUT"])
def update_follow_sop_column(column_id):
    """Follow SOP 페이지 동적 컬럼 수정"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        result = column_service.update_column(column_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-columns/<int:column_id>", methods=["DELETE"])
def delete_follow_sop_column(column_id):
    """Follow SOP 페이지 동적 컬럼 삭제 (비활성화)"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        result = column_service.delete_column(column_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections", methods=["GET"])
def get_follow_sop_sections():
    """Follow SOP 섹션 목록 조회"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        sections = section_service.get_sections()
        return jsonify({"success": True, "sections": sections})
    except Exception as e:
        logging.error(f"Follow SOP 섹션 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections", methods=["POST"])
def add_follow_sop_section():
    """Follow SOP 섹션 추가"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        result = section_service.add_section(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 섹션 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections/<int:section_id>", methods=["PUT"])
def update_follow_sop_section(section_id):
    """Follow SOP 섹션 수정"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        result = section_service.update_section(section_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 섹션 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections/<int:section_id>", methods=["DELETE"])
def delete_follow_sop_section(section_id):
    """Follow SOP 섹션 삭제"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        result = section_service.delete_section(section_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 섹션 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections/reorder", methods=["POST"])
def reorder_follow_sop_sections():
    """Follow SOP 섹션 순서 변경"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        result = section_service.reorder_sections(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 섹션 순서 변경 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Full Process API 엔드포인트
@app.route("/api/full-process-columns", methods=["GET"])
def get_full_process_columns():
    """Full Process 페이지 동적 컬럼 설정 조회"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        columns = column_service.list_columns()
        return jsonify(columns)
    except Exception as e:
        logging.error(f"Full Process 컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-columns", methods=["POST"])
def add_full_process_column():
    """Full Process 페이지 동적 컬럼 추가"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        result = column_service.add_column(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-columns/<int:column_id>", methods=["PUT"])
def update_full_process_column(column_id):
    """Full Process 페이지 동적 컬럼 수정"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        result = column_service.update_column(column_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-columns/<int:column_id>", methods=["DELETE"])
def delete_full_process_column(column_id):
    """Full Process 페이지 동적 컬럼 삭제 (비활성화)"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        result = column_service.delete_column(column_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections", methods=["GET"])
def get_full_process_sections():
    """Full Process 섹션 목록 조회"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        sections = section_service.get_sections()
        return jsonify({"success": True, "sections": sections})
    except Exception as e:
        logging.error(f"Full Process 섹션 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections", methods=["POST"])
def add_full_process_section():
    """Full Process 섹션 추가"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        result = section_service.add_section(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 섹션 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections/<int:section_id>", methods=["PUT"])
def update_full_process_section(section_id):
    """Full Process 섹션 수정"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        result = section_service.update_section(section_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 섹션 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections/<int:section_id>", methods=["DELETE"])
def delete_full_process_section(section_id):
    """Full Process 섹션 삭제"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        result = section_service.delete_section(section_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 섹션 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections/reorder", methods=["POST"])
def reorder_full_process_sections():
    """Full Process 섹션 순서 변경"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        result = section_service.reorder_sections(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 섹션 순서 변경 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500