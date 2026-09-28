"""Navigator data contract and access tests; never import the production app."""
import unittest
from unittest.mock import patch

from flask import Flask
import navigator


def fixture():
    return {'partner_id': 'P1', 'partner_name': 'Partner One', 'site': 'Site A',
            'tier': '1', 'work_name': 'Contract', 'owner_login_id': 'alice',
            'owner_dept_id': 'D1', '완료': 7, '미완료': 2, '기한 초과': 0, '진행중': 1,
            'gate_completed': 2, 'gate_incomplete': 1}


class NavigatorTests(unittest.TestCase):
    def setUp(self):
        self.settings = navigator.load_settings()
        self.settings['queries']['exceptions'] = ''

    def build(self, rows, level=3, user='alice', dept='D1'):
        return navigator.build_dashboard(self.settings, level, user, dept,
                                        lambda sql, source: (rows, list(fixture())))

    def test_scopes_apply_before_all_aggregates(self):
        a = fixture()
        b = dict(a, partner_id='P2', owner_login_id='bob')
        c = dict(a, partner_id='P3', owner_login_id='eve', owner_dept_id='D2')
        for level, expected in [(0, 0), (1, 10), (2, 20), (3, 30)]:
            result = self.build([a, b, c], level)
            self.assertEqual(result['summary']['total'], expected)
            self.assertEqual(sum(s['total'] for s in result['sites']), expected)
            self.assertEqual(sum(p['total'] for p in result['partners']), expected)
        self.assertEqual(self.build([a], 1, '', '')['summary']['total'], 0)
        self.assertEqual(self.build([a], 2, 'alice', 'D2')['summary']['total'], 10)

    def test_status_extension_and_completion_mapping(self):
        self.settings['statuses'].append({'key': '검토대기', 'label': '검토대기', 'color': '#aa66cc', 'completed': False})
        row = dict(fixture(), 검토대기=3)
        result = navigator.build_dashboard(self.settings, 3, runner=lambda *a: ([row], list(row)))
        self.assertEqual(result['summary'], {'partners': 1, 'total': 13,
                         'counts': {'완료': 7, '미완료': 2, '기한 초과': 0, '진행중': 1, '검토대기': 3}})
        self.assertEqual(result['work'][0]['counts']['검토대기'], 3)
        self.assertEqual(result['summary']['counts'], result['sites'][0]['counts'])
        self.assertEqual(result['summary']['counts'], result['partners'][0]['counts'])
        self.assertEqual(result['summary']['counts']['미완료'], 2)

    def test_partner_count_deduplicates_across_work(self):
        result = self.build([fixture(), dict(fixture(), work_name='Training')])
        self.assertEqual(result['summary']['partners'], 1)
        self.assertEqual(result['partners'][0]['total'], 20)

    def test_bad_counts_duplicate_grain_and_gate_fail(self):
        for value in (None, -1, 1.5, float('nan'), float('inf'), 'invalid'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build([dict(fixture(), 완료=value)])
        with self.assertRaises(ValueError):
            self.build([fixture(), fixture()])
        with self.assertRaises(ValueError):
            self.build([dict(fixture(), gate_incomplete=10)])

    def test_missing_columns_even_with_zero_rows(self):
        with self.assertRaises(ValueError):
            navigator.build_dashboard(self.settings, 3, runner=lambda *a: ([], ['partner_id']))
        self.assertEqual(self.build([])['summary']['total'], 0)
        self.assertFalse(self.build([])['exceptions_linked'])

    def test_uppercase_external_columns(self):
        row = {k.upper(): v for k, v in fixture().items()}
        result = navigator.build_dashboard(self.settings, 3, runner=lambda *a: ([row], list(row)))
        self.assertEqual(result['summary']['total'], 10)

    def test_exception_scope_and_private_fields(self):
        self.settings['queries']['exceptions'] = 'EXCEPTIONS'
        row = dict(exception_id='E1', partner_id='P1', partner_name='One', site='A', work_name='Contract',
                   issue='Review', status='Pending', category='Review', owner_name='Alice',
                   owner_login_id='alice', owner_dept_id='D1')
        other = dict(row, exception_id='E2', owner_login_id='bob', owner_dept_id='D2')
        def runner(sql, source):
            return ([row, other], list(row)) if sql == 'EXCEPTIONS' else ([fixture()], list(fixture()))
        result = navigator.build_dashboard(self.settings, 1, 'alice', 'D1', runner)
        self.assertEqual(len(result['exceptions']), 1)
        self.assertNotIn('owner_login_id', result['exceptions'][0])

    def test_permission_blocks_page_and_api_before_queries(self):
        app = Flask(__name__)
        app.register_blueprint(navigator.navigator_bp)
        with patch.object(navigator, 'enforce_permission', return_value=('Forbidden', 403)), patch.object(navigator, 'query_rows') as query:
            client = app.test_client()
            self.assertEqual(client.get('/ax-ehs-navigator').status_code, 403)
            self.assertEqual(client.get('/api/ax-ehs-navigator/dashboard').status_code, 403)
            query.assert_not_called()

    def test_source_failure_is_not_zero_or_sample_fallback(self):
        app = Flask(__name__)
        app.secret_key = 'test-only'
        app.register_blueprint(navigator.navigator_bp)
        with patch.object(navigator, 'enforce_permission', return_value=None), patch.object(navigator, 'get_user_permission_level', return_value=3), patch.object(navigator, 'build_dashboard', side_effect=RuntimeError('query details')):
            response = app.test_client().get('/api/ax-ehs-navigator/dashboard')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('query details', response.get_data(as_text=True))
            self.assertNotIn('summary', response.json)

    def test_menu_admin_and_request_discovery(self):
        from permission_helpers import resolve_menu_code
        from permission_api import _flatten_menu_codes, _build_menu_title_map, _load_request_default_levels
        self.assertEqual(resolve_menu_code('ax-ehs-navigator'), navigator.MENU_CODE)
        self.assertIn(navigator.MENU_CODE, _flatten_menu_codes())
        self.assertIn(navigator.MENU_CODE, _build_menu_title_map())
        for levels in _load_request_default_levels():
            self.assertEqual(levels[navigator.MENU_CODE], {'read': 1, 'write': 0})


if __name__ == '__main__':
    unittest.main()
