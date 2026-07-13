#!/usr/bin/env python3
"""
Update scoring UI for followsop and fullprocess admin pages
"""
import re

def update_scoring_section(file_path):
    """Update the scoring configuration section in the HTML file"""
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace old scoring config section with new one
    old_pattern = r'<!-- 채점 설정 영역.*?</div>\s*</div>\s*</div>'
    new_section = '''        <!-- 채점 설정 영역 -->
        <div class="mb-3" id="scoringConfigField" style="display: none;">
            <label class="form-label">채점 설정</label>
            <div class="d-flex align-items-center gap-2">
                <button type="button" class="btn btn-primary" onclick="openScoringModal()">
                    <i class="bi bi-pencil-square"></i> 채점표 편집
                </button>
                <span id="scoringPreviewLabel" class="text-muted">설정되지 않음</span>
            </div>
            <textarea class="form-control" id="scoringConfig" rows="3" style="display:none;"></textarea>
        </div>'''
    
    content = re.sub(old_pattern, new_section, content, flags=re.DOTALL)
    
    # Check if scoring modal already exists
    if 'id="scoringConfigModal"' not in content:
        # Add the scoring modal before the table config modal
        modal_html = '''
<!-- 채점 설정 모달 -->
<div class="modal fade" id="scoringConfigModal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-xl" style="margin-top: 50px; max-width: 1200px;">
        <div class="modal-content">
            <div class="modal-header bg-light">
                <h5 class="modal-title">
                    <i class="bi bi-clipboard-check"></i> 채점표 설정
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <!-- 탭 메뉴 -->
                <ul class="nav nav-tabs mb-3" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="scoring-items-tab" data-bs-toggle="tab" data-bs-target="#scoring-items" type="button">
                            <i class="bi bi-list-check"></i> 채점 항목
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="grade-criteria-tab" data-bs-toggle="tab" data-bs-target="#grade-criteria" type="button">
                            <i class="bi bi-award"></i> 등급 기준
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="scoring-preview-tab" data-bs-toggle="tab" data-bs-target="#scoring-preview" type="button">
                            <i class="bi bi-eye"></i> 미리보기
                        </button>
                    </li>
                </ul>

                <!-- 탭 내용 -->
                <div class="tab-content">
                    <!-- 채점 항목 탭 -->
                    <div class="tab-pane fade show active" id="scoring-items" role="tabpanel">
                        <div class="alert alert-info mb-3">
                            <i class="bi bi-info-circle"></i> 각 항목별로 단위당 점수를 설정합니다. 음수는 감점, 양수는 가점입니다.
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">기본 점수</label>
                            <input type="number" id="scoringBaseScore" class="form-control" value="100" min="0" style="width: 150px;">
                        </div>

                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h6 class="mb-0">채점 항목</h6>
                            <button type="button" class="btn btn-success btn-sm" onclick="addScoringItem()">
                                <i class="bi bi-plus-circle"></i> 항목 추가
                            </button>
                        </div>

                        <div class="table-responsive">
                            <table class="table table-bordered">
                                <thead class="table-light">
                                    <tr>
                                        <th width="40">순서</th>
                                        <th>항목명</th>
                                        <th width="150">단위당 점수</th>
                                        <th width="120">최대 횟수</th>
                                        <th width="120">최대 점수</th>
                                        <th width="80">작업</th>
                                    </tr>
                                </thead>
                                <tbody id="scoringItemsList">
                                    <!-- 동적으로 생성됨 -->
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- 등급 기준 탭 -->
                    <div class="tab-pane fade" id="grade-criteria" role="tabpanel">
                        <div class="alert alert-info mb-3">
                            <i class="bi bi-info-circle"></i> 점수 범위에 따른 등급 분류 기준을 설정합니다.
                        </div>

                        <div class="row g-3">
                            <div class="col-md-6">
                                <div class="card border-danger">
                                    <div class="card-header bg-danger text-white">
                                        <i class="bi bi-exclamation-triangle"></i> 중대 (Critical)
                                    </div>
                                    <div class="card-body">
                                        <div class="row g-2">
                                            <div class="col-6">
                                                <label class="form-label small">최소값</label>
                                                <input type="number" id="criticalMin" class="form-control" value="-999">
                                            </div>
                                            <div class="col-6">
                                                <label class="form-label small">최대값</label>
                                                <input type="number" id="criticalMax" class="form-control" value="-10">
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card border-warning">
                                    <div class="card-header bg-warning">
                                        <i class="bi bi-exclamation-circle"></i> 주요 (Major)
                                    </div>
                                    <div class="card-body">
                                        <div class="row g-2">
                                            <div class="col-6">
                                                <label class="form-label small">최소값</label>
                                                <input type="number" id="majorMin" class="form-control" value="-9">
                                            </div>
                                            <div class="col-6">
                                                <label class="form-label small">최대값</label>
                                                <input type="number" id="majorMax" class="form-control" value="-5">
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card border-info">
                                    <div class="card-header bg-info text-white">
                                        <i class="bi bi-info-circle"></i> 경미 (Minor)
                                    </div>
                                    <div class="card-body">
                                        <div class="row g-2">
                                            <div class="col-6">
                                                <label class="form-label small">최소값</label>
                                                <input type="number" id="minorMin" class="form-control" value="-4">
                                            </div>
                                            <div class="col-6">
                                                <label class="form-label small">최대값</label>
                                                <input type="number" id="minorMax" class="form-control" value="-1">
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card border-success">
                                    <div class="card-header bg-success text-white">
                                        <i class="bi bi-star"></i> 가점 (Bonus)
                                    </div>
                                    <div class="card-body">
                                        <div class="row g-2">
                                            <div class="col-6">
                                                <label class="form-label small">최소값</label>
                                                <input type="number" id="bonusMin" class="form-control" value="0.1" step="0.1">
                                            </div>
                                            <div class="col-6">
                                                <label class="form-label small">최대값</label>
                                                <input type="number" id="bonusMax" class="form-control" value="999">
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 미리보기 탭 -->
                    <div class="tab-pane fade" id="scoring-preview" role="tabpanel">
                        <div class="alert alert-success mb-3">
                            <i class="bi bi-check-circle"></i> 설정된 채점표 미리보기
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <h6>채점 항목 요약</h6>
                                <div id="scoringItemsSummary" class="border rounded p-3 mb-3">
                                    <!-- 동적으로 생성됨 -->
                                </div>
                            </div>
                            <div class="col-md-6">
                                <h6>등급 기준 요약</h6>
                                <div id="gradeCriteriaSummary" class="border rounded p-3 mb-3">
                                    <!-- 동적으로 생성됨 -->
                                </div>
                            </div>
                        </div>

                        <h6>JSON 설정값</h6>
                        <pre id="scoringJsonPreview" class="border rounded p-3 bg-light" style="max-height: 300px; overflow-y: auto;"></pre>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">취소</button>
                <button type="button" class="btn btn-primary" onclick="saveScoringConfig()">
                    <i class="bi bi-check-lg"></i> 저장
                </button>
            </div>
        </div>
    </div>
</div>

'''
        content = content.replace('<!-- 테이블 설정 모달 -->', modal_html + '<!-- 테이블 설정 모달 -->')
    
    # Write back the updated content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Updated: {file_path}")

# Update both files
files_to_update = [
    'templates/admin-followsop-columns.html',
    'templates/admin-fullprocess-columns.html'
]

for file_path in files_to_update:
    try:
        update_scoring_section(file_path)
    except Exception as e:
        print(f"Error updating {file_path}: {e}")

print("Done!")