"""Accident board controller for Phase 2 refactor."""

from __future__ import annotations

from flask import jsonify, render_template

from controllers import BoardController, BoardControllerConfig


class AccidentController(BoardController):
    """Controller that orchestrates accident board flows."""

    def list_view(self, request):
        filters = self._extract_filters(request)
        page, per_page = self._default_pagination(request)

        context = self.repository.fetch_list_context(filters, (page, per_page))
        template_context = self._build_template_context(**context)
        return render_template(self.config.list_template, **template_context)

    def detail_view(self, request, accident_id):
        context = self.repository.fetch_detail_context(accident_id, request.args.get('popup') == '1')
        if not context:
            return "사고 정보를 찾을 수 없습니다.", 404
        template_context = self._build_template_context(**context)
        return render_template(self.config.detail_template, **template_context)

    def register_view(self, request):
        context = self.repository.fetch_register_context(request.args.get('popup') == '1')
        template_context = self._build_template_context(**context)
        return render_template(self.config.register_template, **template_context)

    def save(self, request):
        return self._format_response(self.repository.save_from_request(request))

    def update(self, request):
        from flask import current_app
        current_app.logger.info("[ACCIDENT_CONTROLLER] update invoked")
        return self._format_response(self.repository.update_from_request(request))

    def _format_response(self, result):
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
            'accident_date_start': request.args.get('accident_date_start'),
            'accident_date_end': request.args.get('accident_date_end'),
            'workplace': (request.args.get('workplace') or '').strip(),
            'accident_grade': (request.args.get('accident_grade') or '').strip(),
        }


def build_accident_config() -> BoardControllerConfig:
    return BoardControllerConfig(
        board_type="accident",
        list_template="partner-accident.html",
        detail_template="accident-detail.html",
        register_template="accident-register.html",
        attachments_enabled=True,
        scoring_enabled=False,
        per_page_default=10,
        extra_context={
            "menu_section": "accident",
        },
    )
