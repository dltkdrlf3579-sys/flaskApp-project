"""Navigator data contract and access tests; never import the production app."""
import unittest
import ast
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock

from flask import Flask
import navigator


def fixture():
    return {'partner_id': 'P1', 'partner_name': 'Partner One', 'site': 'Site A',
            'tier': '1', 'work_name': 'Contract', 'owner_login_id': 'alice',
            'owner_dept_id': 'D1', '완료': 7, '미완료': 2, '기한초과': 0, '진행중': 1,
            'gate_completed': 2, 'gate_incomplete': 1}


class NavigatorTests(unittest.TestCase):
    def setUp(self):
        self.settings = navigator.load_settings()
        # Preserve regression coverage for the existing deployed workload format.
        self.settings['works'] = []
        self.settings['queries']['workload'] = 'WORKLOAD'
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
                         'counts': {'완료': 7, '미완료': 2, '기한초과': 0, '진행중': 1, '검토대기': 3}})
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
        from permission_api import _flatten_menu_codes, _build_menu_title_map, _default_levels_for_request
        self.assertEqual(resolve_menu_code('ax-ehs-navigator'), navigator.MENU_CODE)
        self.assertIn(navigator.MENU_CODE, _flatten_menu_codes())
        self.assertIn(navigator.MENU_CODE, _build_menu_title_map())
        self.assertEqual(_build_menu_title_map()[navigator.MENU_CODE], 'AX EHS Navigator')
        for company_id in ('C100', 'C10', None):
            self.assertEqual(_default_levels_for_request(navigator.MENU_CODE, 'read', company_id, {}, {}), (1, 0))
            self.assertEqual(_default_levels_for_request(navigator.MENU_CODE, 'read_write', company_id, {}, {}), (1, 1))

    def test_actual_admin_menu_api_exposes_navigator_name(self):
        # Run the actual route body without importing app.py's startup hooks.
        from flask import jsonify
        from config.menu import MENU_CONFIG
        from permission_helpers import resolve_menu_code
        tree = ast.parse(Path('app.py').read_text(encoding='utf-8'))
        route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'api_menus')
        route.decorator_list = []
        namespace = {'MENU_CONFIG': MENU_CONFIG, 'resolve_menu_code': resolve_menu_code, 'jsonify': jsonify}
        exec(compile(ast.Module(body=[route], type_ignores=[]), 'app.py', 'exec'), namespace)
        app = Flask(__name__)
        with app.app_context():
            menus = namespace['api_menus']().get_json()
        self.assertEqual([m['name'] for m in menus if m['code'] == navigator.MENU_CODE], ['AX EHS Navigator'])

    def test_hidden_menus_removed_for_every_topbar_path(self):
        import permission_helpers as helpers
        from config.menu import MENU_CONFIG
        all_codes = [{'code': helpers.resolve_menu_code(s['url'])} for m in MENU_CONFIG for s in m['submenu']]
        app = Flask(__name__)
        with app.test_request_context('/'):
            for enabled, admin, fail in [(True, False, False), (True, True, False),
                                          (False, False, False), (True, False, True)]:
                with self.subTest(enabled=enabled, admin=admin, fail=fail), \
                     patch.object(helpers, 'PERMISSION_ENABLED', enabled), \
                     patch.object(helpers, 'is_super_admin', return_value=admin), \
                     patch.object(helpers, 'get_user_accessible_menus', return_value=all_codes,
                                  side_effect=RuntimeError('test') if fail else None):
                    menus = helpers.build_user_menu_config()
                    slugs = {s['url'] for m in menus for s in m['submenu']}
                    self.assertTrue({'ai-assistant', 'subcontract-approval', 'subcontract-report'}.isdisjoint(slugs))
                    self.assertIn('ax-ehs-navigator', slugs)
        # Hiding navigation must not remove grantable permission definitions.
        from permission_api import _flatten_menu_codes
        self.assertTrue({'AI_ASSISTANT', 'SUBCONTRACT_APPROVAL', 'SUBCONTRACT_REPORT'}.issubset(_flatten_menu_codes()))

    def test_admin_can_save_navigator_for_user_and_department(self):
        import permission_api
        app = Flask(__name__)
        app.secret_key = 'test-only'
        permission_api.register_permission_routes(app)
        client = app.test_client()
        conn = MagicMock()
        conn.cursor.return_value.fetchone.return_value = {'dept_code': 'D1', 'dept_full_path': 'Demo'}
        with patch.object(permission_api, 'get_db_connection', return_value=conn), patch.object(permission_api, 'is_super_admin', return_value=False):
            denied = client.post('/api/menu-roles/batch-update', json={'changes': []})
            self.assertEqual(denied.status_code, 403)
            conn.cursor.assert_not_called()
            with client.session_transaction() as sess:
                sess['admin_authenticated'] = True
                sess['user_id'] = 'demo_admin'
            for endpoint, identity in [('/api/menu-roles/batch-update', {'login_id': 'demo_user'}),
                                       ('/api/dept-roles/batch-update', {'dept_id': 'D1'})]:
                response = client.post(endpoint, json={'changes': [{**identity, 'menu_code': navigator.MENU_CODE,
                                                                    'read_level': 3, 'write_level': 0}]})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['count'], 1)
            inserts = [call for call in conn.cursor.return_value.execute.call_args_list if 'INSERT INTO' in call.args[0]]
            self.assertEqual(len(inserts), 2)
            self.assertTrue(all(navigator.MENU_CODE in call.args[1] for call in inserts))


class NavigatorWorkScopeTests(unittest.TestCase):
    def setUp(self):
        self.settings = navigator.load_settings()
        self.settings['queries']['exceptions'] = ''
        self.settings['works'] = [
            {'id': 'contract', 'name': 'Contract', 'scope': 'company', 'enabled': True, 'query': 'COMPANY'},
            {'id': 'report', 'name': 'Report', 'scope': 'site', 'enabled': False, 'query': 'SITE'},
        ]
        self.calls = []

    def company(self, **changes):
        row = fixture()
        for key in ('site', 'work_name', 'gate_completed', 'gate_incomplete'):
            row.pop(key)
        return {**row, **changes}

    def build(self, company_rows, site_rows=None, level=3, user='alice', dept='D1'):
        self.settings['works'][1]['enabled'] = site_rows is not None
        def runner(sql, source):
            self.calls.append((sql, source))
            if sql == 'COMPANY':
                return company_rows, list(self.company())
            if sql == 'SITE' and site_rows is not None:
                return site_rows, list(fixture())
            raise AssertionError('Unexpected query')
        return navigator.build_dashboard(self.settings, level, user, dept, runner)

    def test_company_work_without_site_and_optional_gate(self):
        result = self.build([self.company()])
        self.assertEqual(result['summary']['total'], 10)
        self.assertEqual(result['sites'], [])
        self.assertFalse(result['site_work_linked'])
        self.assertEqual(result['gate'], {'completed': 0, 'incomplete': 0})
        self.assertEqual(result['work'][0]['scope'], 'company')
        partner = result['partners'][0]
        self.assertEqual(partner['sites'], [])
        self.assertEqual(partner['company_work'][0]['total'], 10)
        self.assertEqual(partner['site_work'], [])
        self.assertEqual(self.calls, [('COMPANY', 'sample_postgres')])

    def test_company_plus_two_sites_preserves_grain_in_details(self):
        result = self.build([self.company()], [fixture(), dict(fixture(), site='Site B')])
        self.assertEqual(result['summary']['partners'], 1)
        self.assertEqual(result['summary']['total'], 30)
        self.assertEqual(sum(w['total'] for w in result['work']), 30)
        self.assertEqual(sum(s['total'] for s in result['sites']), 20)
        partner = result['partners'][0]
        self.assertEqual(partner['total'], 30)
        self.assertEqual(sum(w['total'] for w in partner['company_work']), 10)
        self.assertEqual([(w['name'], w['site'], w['total']) for w in partner['site_work']],
                         [('Report', 'Site A', 10), ('Report', 'Site B', 10)])
        self.assertEqual(partner['sites'], ['Site A', 'Site B'])
        self.assertEqual(result['gate'], {'completed': 4, 'incomplete': 2})
        self.assertEqual(len(self.calls), 2)

    def test_company_data_cannot_be_replicated_per_site(self):
        with self.assertRaises(ValueError):
            self.build([self.company(site='A'), self.company(site='B')])

    def test_site_work_requires_site_even_for_empty_result_schema(self):
        with self.assertRaises(ValueError):
            self.build([self.company()], [dict(fixture(), site='')])
        self.settings['works'][1]['enabled'] = True
        with self.assertRaises(ValueError):
            navigator.build_dashboard(self.settings, 3,
                runner=lambda *args: ([], list(self.company())))

    def test_permissions_filter_each_work_before_aggregation(self):
        companies = [self.company(), self.company(partner_id='P2', owner_login_id='bob'),
                     self.company(partner_id='P3', owner_login_id='eve', owner_dept_id='D2')]
        sites = [fixture(), dict(fixture(), partner_id='P2', owner_login_id='bob'),
                 dict(fixture(), partner_id='P3', owner_login_id='eve', owner_dept_id='D2')]
        for level, expected in [(0, 0), (1, 20), (2, 40), (3, 60)]:
            with self.subTest(level=level):
                result = self.build(companies, sites, level)
                self.assertEqual(result['summary']['total'], expected)
                self.assertEqual(sum(s['total'] for s in result['sites']), expected // 2)
                self.assertEqual(sum(p['total'] for p in result['partners']), expected)
        self.assertEqual(self.build(companies, sites, 2, '', '')['summary']['total'], 0)

    def test_new_status_in_every_work_and_detail(self):
        self.settings['statuses'].append({'key': '검토대기', 'label': '검토대기', 'color': '#aa66cc', 'completed': False})
        self.settings['works'][1]['enabled'] = True
        rows = {'COMPANY': dict(self.company(), 검토대기=3), 'SITE': dict(fixture(), 검토대기=5)}
        result = navigator.build_dashboard(self.settings, 3, runner=lambda sql, source: ([rows[sql]], list(rows[sql])))
        self.assertEqual(result['summary']['total'], 28)
        self.assertEqual(result['summary']['counts']['검토대기'], 8)
        self.assertEqual(result['sites'][0]['counts']['검토대기'], 5)
        partner = result['partners'][0]
        self.assertEqual(partner['counts']['검토대기'], 8)
        self.assertEqual(partner['company_work'][0]['counts']['검토대기'], 3)
        self.assertEqual(partner['site_work'][0]['counts']['검토대기'], 5)
        with self.assertRaises(ValueError):
            self.build([self.company()], [fixture()])

    def test_gate_columns_supplied_together_and_values_validated(self):
        for row in (self.company(gate_completed=1),
                    self.company(gate_completed=1, gate_incomplete=9)):
            with self.subTest(row=row), self.assertRaises(ValueError):
                navigator.build_dashboard(self.settings, 3, runner=lambda *args: ([row], list(row)))

    def test_company_exception_can_omit_site_and_remains_scoped(self):
        self.settings['queries']['exceptions'] = 'EXCEPTIONS'
        exception = dict(exception_id='E1', partner_id='P1', partner_name='One', work_name='Contract',
                         issue='Review', status='미완료', category='Review', owner_name='Alice',
                         owner_login_id='alice', owner_dept_id='D1')
        def runner(sql, source):
            return ([exception], list(exception)) if sql == 'EXCEPTIONS' else ([self.company()], list(self.company()))
        result = navigator.build_dashboard(self.settings, 1, 'alice', 'D1', runner)
        self.assertEqual(result['exceptions'][0]['site'], '')
        self.assertNotIn('owner_login_id', result['exceptions'][0])
        self.assertEqual(navigator.build_dashboard(self.settings, 1, 'bob', 'D2', runner)['exceptions'], [])

    def test_empty_site_query_is_linked_and_failed_query_is_not_ignored(self):
        result = self.build([self.company()], [])
        self.assertTrue(result['site_work_linked'])
        self.assertEqual(result['sites'], [])
        def runner(sql, source):
            if sql == 'SITE':
                raise RuntimeError('Unavailable site query')
            return [self.company()], list(self.company())
        with self.assertRaises(RuntimeError):
            navigator.build_dashboard(self.settings, 3, runner=runner)

    def test_all_works_disabled_are_not_queried(self):
        for work in self.settings['works']:
            work['enabled'] = False
        def runner(*args):
            raise AssertionError('Disabled query ran')
        result = navigator.build_dashboard(self.settings, 3, runner=runner)
        self.assertEqual(result['summary']['total'], 0)
        self.assertFalse(result['site_work_linked'])

    def test_qadb_source_shared_by_all_enabled_work_queries(self):
        self.settings['source'] = 'qadb'
        result = self.build([self.company()], [fixture()])
        self.assertFalse(result['sample'])
        self.assertEqual(self.calls, [('COMPANY', 'qadb'), ('SITE', 'qadb')])

    def test_work_ids_keep_identical_display_names_separate(self):
        self.settings['works'][1]['name'] = 'Contract'
        result = self.build([self.company()], [fixture()])
        self.assertEqual([(w['id'], w['scope'], w['total']) for w in result['work']],
                         [('contract', 'company', 10), ('report', 'site', 10)])
        self.assertEqual(len(result['partners'][0]['company_work']), 1)
        self.assertEqual(len(result['partners'][0]['site_work']), 1)

    def test_config_loads_legacy_and_korean_ids_without_sql_interpolation(self):
        prefix = navigator.CONFIG_PATH.read_text(encoding='utf-8-sig').split('[WORK:', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'navigator.ini'
            path.write_text(prefix + '[QUERIES]\nworkload = SELECT legacy\n', encoding='utf-8')
            legacy = navigator.load_settings(path)
            self.assertEqual(legacy['works'], [])
            self.assertEqual(legacy['queries']['workload'], 'SELECT legacy')
            sql = "SELECT value FROM example WHERE value LIKE '10%'"
            path.write_text(prefix + '[WORK:계약평가]\nscope = company\nquery = ' + sql, encoding='utf-8')
            work = navigator.load_settings(path)['works'][0]
            self.assertEqual((work['id'], work['name'], work['query']), ('계약평가', '계약평가', sql))
            path.write_text(prefix + '[WORK:future]\nscope = site\nenabled = false\n', encoding='utf-8')
            self.assertFalse(navigator.load_settings(path)['works'][0]['enabled'])
            path.write_text(prefix + '[WORK:future]\nscope = site\nenabled = true\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                navigator.load_settings(path)

    def test_default_config_and_invalid_scope_duplicate_id_or_mixed_format(self):
        text = navigator.CONFIG_PATH.read_text(encoding='utf-8-sig')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'navigator.ini'
            for content in (text.replace('scope = company', 'scope = unknown'),
                            text.replace('[WORK:subcontract_report]', '[WORK:CONTRACT_EVALUATION]'),
                            text.replace('[QUERIES]', '[QUERIES]\nworkload = SELECT 1')):
                path.write_text(content, encoding='utf-8')
                with self.subTest(content=content[:80]), self.assertRaises(ValueError):
                    navigator.load_settings(path)
        works = navigator.load_settings()['works']
        self.assertEqual([w['scope'] for w in works], ['company', 'site', 'site'])
        self.assertEqual([w['enabled'] for w in works], [True, False, False])


if __name__ == '__main__':
    unittest.main()
