from datetime import datetime, timezone
from flask import request, redirect, session, current_app

from . import sso_bp
from .auth_handler import SSOAuthHandler


auth_handler = SSOAuthHandler()


@sso_bp.before_app_request
def _init_auth_handler():
    """Ensure auth handler initialized once per app.

    Note: Some Flask versions don't support before_app_first_request on Blueprint.
    """
    if getattr(auth_handler, "_initialized", False):
        return
    try:
        auth_handler.init_app(current_app)
        setattr(auth_handler, "_initialized", True)
    except Exception as e:
        # Do not block the request; log and continue
        try:
            current_app.logger.warning(f"SSO handler init skipped: {e}")
        except Exception:
            pass


@sso_bp.route('/auth')
def sso_auth():
    """Start SSO auth by redirecting to IdP."""
    url = auth_handler.generate_auth_url()
    return redirect(url)


@sso_bp.route('/callback', methods=['POST'])
def sso_callback():
    """Handle IdP POST back with id_token."""
    try:
        id_token = request.form.get('id_token')
        state = request.form.get('state')

        # CSRF state validation
        if state != session.get('sso_state'):
            raise ValueError('Invalid state parameter')

        claims = auth_handler.validate_token(id_token)

        # Extract user info (adjust claim names to your IdP)
        user_info = {
            # sso_id (unique key)
            'sso_id': (
                claims.get('unique_name') or claims.get('Unique_Name') or
                claims.get('sub') or ''
            ),
            # login id
            'login_id': (
                claims.get('loginid') or claims.get('LoginId') or
                claims.get('preferred_username') or ''
            ),
            # email
            'email': (
                claims.get('mail') or claims.get('email') or ''
            ),
            # display name
            'name': (
                claims.get('username') or claims.get('Username') or
                claims.get('name') or ''
            ),
            # department name
            'department': (
                claims.get('deptname') or claims.get('DeptName') or
                claims.get('department') or ''
            ),
            # grade / title
            'grade': (
                claims.get('grdname') or claims.get('Grade') or
                claims.get('job_title') or ''
            ),
            # optional additional fields (not persisted by default)
            'dept_id': claims.get('DeptId') or claims.get('deptid') or '',
            'int_code': claims.get('IntCode') or claims.get('intcode') or '',
            'int_name': claims.get('IntName') or claims.get('intname') or '',
        }

        user = _create_or_update_user(user_info)

        # Build session
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['department'] = user.get('department', '')
        session['grade'] = user.get('grade', '')
        session['sso_id'] = user_info.get('sso_id')
        # expose common extras for UI (read-only)
        session['login_id'] = user_info.get('login_id')
        session['dept_name'] = user_info.get('department') or user_info.get('int_name')
        session['dept_id'] = user_info.get('dept_id')
        # Backward-compatible aliases (CamelCase keys)
        session['LoginId'] = session.get('login_id')
        session['Username'] = session.get('user_name')
        session['DeptName'] = session.get('dept_name')
        session['DeptId'] = session.get('dept_id')
        session['IntCode'] = user_info.get('int_code')
        session['IntName'] = user_info.get('int_name')

        # Token expiry (exp is seconds since epoch)
        exp_ts = claims.get('exp')
        if exp_ts:
            try:
                exp_iso = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc).isoformat()
                session['token_expires'] = exp_iso
            except Exception:
                pass

        # Clear temp
        session.pop('sso_nonce', None)
        session.pop('sso_state', None)
        session.pop('sso_timestamp', None)

        next_url = session.pop('next_url', '/') or '/'
        return redirect(next_url)

    except Exception as e:
        current_app.logger.error(f"SSO callback error: {e}")
        return (f"인증 실패: {str(e)}", 401)


@sso_bp.route('/logout')
def sso_logout():
    """Clear local session and optionally redirect to IdP logout."""
    session.clear()
    logout_url = current_app.config.get('SSO_LOGOUT_URL')
    if logout_url:
        return redirect(logout_url)
    return redirect('/')


@sso_bp.route('/dev-login', methods=['GET', 'POST'])
def sso_dev_login():
    """Dev-only SSO sample login form.

    - Requires [SSO] sso_enabled = false
    - When submitted, seeds session with provided fields and redirects to next_url
    """
    import configparser
    from flask import render_template

    cfg = configparser.ConfigParser()
    cfg.read('config.ini', encoding='utf-8')
    if cfg.getboolean('SSO', 'sso_enabled', fallback=False):
        return ("Not available in production", 404)

    if request.method == 'POST':
        login_id = request.form.get('LoginId') or request.form.get('login_id') or 'dev_user'
        username = request.form.get('Username') or request.form.get('user_name') or '개발자'
        dept_name = request.form.get('DeptName') or request.form.get('dept_name') or '개발팀'
        dept_id = request.form.get('DeptId') or request.form.get('dept_id') or ''
        int_code = request.form.get('IntCode') or request.form.get('int_code') or ''
        int_name = request.form.get('IntName') or request.form.get('int_name') or ''

        # seed session
        session['user_id'] = login_id
        session['user_name'] = username
        session['department'] = dept_name
        session['grade'] = session.get('grade', '')
        session['login_id'] = login_id
        session['LoginId'] = login_id
        session['Username'] = username
        session['dept_name'] = dept_name
        session['DeptName'] = dept_name
        session['dept_id'] = dept_id
        session['DeptId'] = dept_id
        session['IntCode'] = int_code
        session['IntName'] = int_name

        next_url = session.pop('next_url', '/') or '/'
        return redirect(next_url)

    # GET render simple form
    sample = {
        'LoginId': session.get('LoginId') or cfg.get('SSO', 'dev_user_id', fallback='dev_user'),
        'Username': session.get('Username') or cfg.get('SSO', 'dev_user_name', fallback='개발자'),
        'DeptName': session.get('DeptName') or cfg.get('SSO', 'dev_department', fallback='개발팀'),
        'DeptId': session.get('DeptId') or 'D001',
        'IntCode': session.get('IntCode') or 'INT01',
        'IntName': session.get('IntName') or '인터널',
    }
    return render_template('sso-dev-login.html', sample=sample)


@sso_bp.route('/not-configured')
def sso_not_configured():
    from flask import render_template
    return render_template('sso-not-configured.html')

def _create_or_update_user(user_info):
    """Ensure user exists in person_master and return id/name/etc.

    Adds SSO-specific columns if present in schema.
    """
    from db_connection import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    # detect available columns
    available_cols = set()
    try:
        if getattr(conn, 'is_postgres', False):
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='person_master'
            """)
            available_cols = {row[0] for row in cursor.fetchall()}
        else:
            cursor.execute("PRAGMA table_info(person_master)")
            available_cols = {row[1] for row in cursor.fetchall()}
    except Exception:
        available_cols = set()

    try:
        # Look up by sso_id if column exists, else fallback to email/login_id
        id_field = 'sso_id' if 'sso_id' in available_cols else ('login_id' if 'login_id' in available_cols else 'email')
        id_value = user_info.get('sso_id') if id_field == 'sso_id' else (
            user_info.get('login_id') if id_field == 'login_id' else user_info.get('email')
        )

        cursor.execute(f"""
            SELECT id, name, department, COALESCE(grade, '')
            FROM person_master
            WHERE {id_field} = ?
        """, (id_value,))
        row = cursor.fetchone()

        if row:
            # Update
            set_parts = []
            params = []
            for col_key, val_key in (
                ('name', 'name'),
                ('email', 'email'),
                ('department', 'department'),
                ('grade', 'grade'),
                ('login_id', 'login_id'),
                ('sso_id', 'sso_id'),
            ):
                if col_key in available_cols:
                    set_parts.append(f"{col_key} = ?")
                    params.append(user_info.get(val_key, ''))
            if 'last_login' in available_cols:
                set_parts.append("last_login = CURRENT_TIMESTAMP")
            sql = f"UPDATE person_master SET {', '.join(set_parts)} WHERE {id_field} = ?"
            params.append(id_value)
            cursor.execute(sql, tuple(params))
            user_id = row[0]
        else:
            # Insert
            columns = ['name', 'department']
            values = [user_info.get('name', ''), user_info.get('department', '')]
            if 'position' in available_cols:
                columns.append('position'); values.append('')
            if 'company_name' in available_cols:
                columns.append('company_name'); values.append('')
            columns.extend([c for c in ('phone', 'email') if c in available_cols])
            for c in ('phone', 'email'):
                if c in available_cols:
                    values.append(user_info.get(c, ''))
            for c in ('grade', 'login_id', 'sso_id'):
                if c in available_cols:
                    columns.append(c); values.append(user_info.get(c, ''))
            if 'created_at' in available_cols:
                columns.append('created_at'); values.append(None)  # DEFAULT CURRENT_TIMESTAMP may handle
            if 'last_login' in available_cols:
                columns.append('last_login'); values.append(None)
            if 'is_active' in available_cols:
                columns.append('is_active'); values.append(1)
            if 'is_sso_user' in available_cols:
                columns.append('is_sso_user'); values.append(1)

            placeholders = ','.join(['?'] * len(values))
            sql = f"INSERT INTO person_master ({', '.join(columns)}) VALUES ({placeholders})"
            cursor.execute(sql, tuple(values))
            try:
                user_id = cursor.lastrowid
            except Exception:
                # Postgres fallback (RETURNING not used in compat insert path): fetch currval
                cursor.execute("SELECT MAX(id) FROM person_master")
                user_id = cursor.fetchone()[0]

        conn.commit()
        return {
            'id': user_id,
            'name': user_info.get('name', ''),
            'department': user_info.get('department', ''),
            'grade': user_info.get('grade', ''),
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
