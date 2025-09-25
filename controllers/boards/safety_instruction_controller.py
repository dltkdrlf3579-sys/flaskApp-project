"""Safety Instruction board controller for Phase 2 refactor."""

from __future__ import annotations

from flask import jsonify, render_template

from controllers import BoardController, BoardControllerConfig


class SafetyInstructionController(BoardController):
    """Controller that encapsulates safety instruction board behaviour."""

    def list_view(self, request):
        filters = self._extract_filters(request)
        page, per_page = self._default_pagination(request)

        context = self.repository.fetch_list_context(filters, (page, per_page))
        template_context = self._build_template_context(**context)
        return render_template(self.config.list_template, **template_context)

    def detail_view(self, request, issue_number: str):
        context = self.repository.fetch_detail_context(
            issue_number,
            request.args.get('popup') == '1',
        )
        if not context:
            return "환경안전 지시서를 찾을 수 없습니다.", 404
        template_context = self._build_template_context(**context)
        return render_template(self.config.detail_template, **template_context)

    def register_view(self, request):
        context = self.repository.fetch_register_context(
            request.args.get('popup') == '1'
        )
        template_context = self._build_template_context(**context)
        return render_template(self.config.register_template, **template_context)

    def save(self, request):
        result = self.repository.save_from_request(request)

        if isinstance(result, tuple):
            payload = result[0]
            status = result[1] if len(result) > 1 else 200
            headers = result[2] if len(result) > 2 else None

            if isinstance(payload, (dict, list)):
                response = jsonify(payload)
                if headers:
                    return response, status, headers
                return response, status
            return result

        if isinstance(result, (dict, list)):
            return jsonify(result)

        return result

    def update(self, request):
        result = self.repository.update_from_request(request)

        if isinstance(result, tuple):
            payload = result[0]
            status = result[1] if len(result) > 1 else 200
            headers = result[2] if len(result) > 2 else None

            if isinstance(payload, (dict, list)):
                response = jsonify(payload)
                if headers:
                    return response, status, headers
                return response, status
            return result

        if isinstance(result, (dict, list)):
            return jsonify(result)

        return result

    def _extract_filters(self, request):
        return {
            'company_name': (request.args.get('company_name') or '').strip(),
            'business_number': (request.args.get('business_number') or '').strip(),
            'violation_date_from': request.args.get('violation_date_from'),
            'violation_date_to': request.args.get('violation_date_to'),
        }


def build_safety_instruction_config() -> BoardControllerConfig:
    return BoardControllerConfig(
        board_type="safety_instruction",
        list_template="safety-instruction.html",
        detail_template="safety-instruction-detail.html",
        register_template="safety-instruction-register.html",
        attachments_enabled=True,
        scoring_enabled=False,
        per_page_default=10,
        extra_context={
            "menu_section": "safety_instruction",
            "permission_code": "SAFETY_INSTRUCTION",
        },
    )
