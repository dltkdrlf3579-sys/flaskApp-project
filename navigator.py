"""Read-only Navigator: configured queries, scoped counts, no persisted snapshot."""
from collections import Counter
import configparser
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import logging
from pathlib import Path
import re

from flask import Blueprint, jsonify, render_template, session
from permission_helpers import enforce_permission, get_user_permission_level

navigator_bp = Blueprint('navigator', __name__)
MENU_CODE = 'AX_EHS_NAVIGATOR'
CONFIG_PATH = Path(__file__).with_name('navigator_config.ini')
logger = logging.getLogger(__name__)


def load_settings(path=None):
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    with open(path or CONFIG_PATH, encoding='utf-8-sig') as stream:
        config.read_file(stream)
    source = config.get('NAVIGATOR', 'source')
    if source not in {'qadb', 'sample_postgres'}:
        raise ValueError('Unsupported Navigator source')
    statuses = []
    completed = {s.strip().casefold() for s in config.get('NAVIGATOR', 'completed_columns').split(',')}
    for name, color in config.items('STATUS_COLUMNS'):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color.strip()):
            raise ValueError('Invalid status color')
        statuses.append({'key': name.casefold(), 'label': name, 'color': color.strip(),
                         'completed': name.casefold() in completed})
    keys = [s['key'] for s in statuses]
    reserved = {'partner_id', 'partner_name', 'site', 'tier', 'work_name',
                'owner_login_id', 'owner_dept_id', 'gate_completed', 'gate_incomplete'}
    if (not statuses or len(keys) != len(set(keys)) or reserved.intersection(keys)
            or not completed or not completed.issubset(keys)):
        raise ValueError('Invalid status columns')
    queries = {name: config.get('QUERIES', name, fallback='').strip()
               for name in ('workload', 'exceptions')}
    if not queries['workload']:
        raise ValueError('Missing workload query')
    return {'source': source, 'statuses': statuses, 'queries': queries}


def query_rows(sql, source):
    # SQL is trusted deployment configuration, never supplied by HTTP parameters.
    if source == 'qadb':
        from database_config import execute_SQL
        frame = execute_SQL(sql)
        return frame.to_dict(orient='records'), list(frame.columns)
    from db_connection import get_db_connection
    conn = get_db_connection()
    try:
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute('SET LOCAL statement_timeout = 15000')
        with conn.cursor() as cursor:
            cursor.execute(sql)
            columns = [column[0] for column in cursor.description]
            return [dict(row) for row in cursor.fetchall()], columns
    finally:
        conn.rollback()
        conn.close()


def normalize_rows(rows, columns, required):
    names = [str(name).casefold() for name in columns]
    if len(names) != len(set(names)) or not set(required).issubset(names):
        raise ValueError('Missing or duplicate Navigator query columns')
    return [{str(k).casefold(): v for k, v in row.items()} for row in rows]


def text_value(value):
    if value is None:
        return ''
    # pandas may return NaN/NaT for missing IDs. They must never match a scope.
    if str(value).strip().lower() in {'nan', 'nat', '<na>'}:
        return ''
    return str(value).strip()


def scope_rows(rows, level, user_id, dept_id):
    if level >= 3:
        return rows
    if level <= 0:
        return []
    user_id, dept_id = text_value(user_id), text_value(dept_id)
    return [row for row in rows
            if (user_id and text_value(row.get('owner_login_id')) == user_id)
            or (level == 2 and dept_id and text_value(row.get('owner_dept_id')) == dept_id)]


def count_value(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number != number.to_integral_value():
            raise ValueError('Invalid count')
        if number > 9007199254740991:
            raise ValueError('Count exceeds browser integer precision')
        return int(number)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid count') from exc


def build_dashboard(settings, level, user_id='', dept_id='', runner=query_rows):
    statuses = settings['statuses']
    keys = [s['key'] for s in statuses]
    required = ['partner_id', 'partner_name', 'site', 'tier', 'work_name',
                'owner_login_id', 'owner_dept_id', 'gate_completed', 'gate_incomplete', *keys]
    rows, columns = runner(settings['queries']['workload'], settings['source'])
    rows = scope_rows(normalize_rows(rows, columns, required), level, user_id, dept_id)
    groups = {'work': {}, 'sites': {}, 'partners': {}}
    total = {key: 0 for key in keys}
    gate = {'completed': 0, 'incomplete': 0}
    seen = set()
    for row in rows:
        identity = tuple(text_value(row[k]) for k in (
            'partner_id', 'site', 'work_name', 'owner_login_id', 'owner_dept_id'))
        if not all(text_value(row[k]) for k in ('partner_id', 'partner_name', 'site', 'work_name', 'tier')):
            raise ValueError('Missing workload identity')
        if identity in seen:
            raise ValueError('Duplicate workload grain')
        seen.add(identity)
        counts = {key: count_value(row[key]) for key in keys}
        completed = sum(counts[s['key']] for s in statuses if s['completed'])
        gc, gi = count_value(row['gate_completed']), count_value(row['gate_incomplete'])
        if gc > completed or gi > sum(counts.values()) - completed:
            raise ValueError('Gate counts must be a subset of workload counts')
        gate['completed'] += gc
        gate['incomplete'] += gi
        for key in keys:
            total[key] += counts[key]
        for group_name, group_key in [('work', identity[2]), ('sites', identity[1]), ('partners', identity[0])]:
            entry = groups[group_name].setdefault(group_key, {
                'id': group_key, 'name': text_value(row['partner_name']) if group_name == 'partners' else group_key,
                'counts': {key: 0 for key in keys}, 'gate_completed': 0, 'gate_incomplete': 0,
                'sites': set(), 'tiers': set(), 'work': {},
            })
            for key in keys:
                entry['counts'][key] += counts[key]
            entry['gate_completed'] += gc
            entry['gate_incomplete'] += gi
            entry['sites'].add(identity[1])
            entry['tiers'].add(text_value(row['tier']))
            if group_name == 'partners':
                work_counts = entry['work'].setdefault(identity[2], {key: 0 for key in keys})
                for key in keys:
                    work_counts[key] += counts[key]
    for mapping in groups.values():
        for entry in mapping.values():
            entry['sites'] = sorted(entry['sites'])
            entry['tiers'] = sorted(entry['tiers'])
            entry['total'] = sum(entry['counts'].values())
    exceptions = []
    exceptions_linked = bool(settings['queries']['exceptions'])
    if exceptions_linked:
        erows, ecolumns = runner(settings['queries']['exceptions'], settings['source'])
        erequired = ['exception_id', 'partner_id', 'partner_name', 'site', 'work_name',
                     'issue', 'status', 'category', 'owner_name', 'owner_login_id', 'owner_dept_id']
        erows = scope_rows(normalize_rows(erows, ecolumns, erequired), level, user_id, dept_id)
        exception_ids = set()
        for row in erows:
            entry = {key: text_value(row[key]) for key in erequired}
            if not entry['exception_id'] or entry['exception_id'] in exception_ids:
                raise ValueError('Missing or duplicate exception ID')
            exception_ids.add(entry['exception_id'])
            # Only return public display fields after scope filtering.
            exceptions.append({k: v for k, v in entry.items() if not k.startswith('owner_') or k == 'owner_name'})
    return {
        'statuses': statuses, 'sample': settings['source'] == 'sample_postgres',
        'queried_at': datetime.now(timezone(timedelta(hours=9))).strftime('%Y.%m.%d %H:%M'),
        'summary': {'partners': len(groups['partners']), 'total': sum(total.values()), 'counts': total},
        'gate': gate, 'work': list(groups['work'].values()), 'sites': list(groups['sites'].values()),
        'partners': list(groups['partners'].values()), 'exceptions': exceptions,
        'exceptions_linked': exceptions_linked,
        'categories': dict(Counter(e['category'] for e in exceptions)),
    }


@navigator_bp.get('/ax-ehs-navigator')
def dashboard():
    denied = enforce_permission(MENU_CODE, 'view')
    if denied is not None:
        return denied
    from audit_logger import record_menu_view
    record_menu_view(MENU_CODE)
    return render_template('navigator.html')


@navigator_bp.get('/api/ax-ehs-navigator/dashboard')
def dashboard_data():
    denied = enforce_permission(MENU_CODE, 'view', response_type='json')
    if denied is not None:
        return denied
    try:
        payload = build_dashboard(load_settings(), get_user_permission_level(MENU_CODE, 'read'),
                                  session.get('user_id'), session.get('deptid'))
        response = jsonify(payload)
        response.headers['Cache-Control'] = 'no-store'
        return response
    except Exception:
        logger.exception('Navigator dashboard query failed')
        return jsonify({'error': '현황을 불러오지 못했습니다. 조회 설정과 데이터 연결을 확인해 주세요.'}), 503
