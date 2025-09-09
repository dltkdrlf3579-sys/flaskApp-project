from datetime import datetime, timezone
import configparser
from flask import session, request, redirect


def check_sso_authentication():
    """Before-request guard to enforce SSO login when enabled.

    - Skips static paths and the SSO endpoints themselves
    - In dev (sso_enabled=false), seeds a dev user into session if missing
    """
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    sso_enabled = config.getboolean('SSO', 'sso_enabled', fallback=False)

    # Excluded paths
    excluded_prefixes = (
        '/sso/',
        '/static/',
        '/favicon.ico',
        '/_debug/',
    )
    if request.path.startswith(excluded_prefixes):
        return None

    # Skip non-HTML data endpoints that may be called pre-login (adjust if needed)
    # Keep /api open; UI will redirect first load anyway
    if request.path.startswith('/api/'):
        return None

    if not sso_enabled:
        # If dev simulate-flow is ON, show a dev login form instead of auto-seeding
        dev_simulate = config.getboolean('SSO', 'dev_simulate_flow', fallback=False)
        if dev_simulate and 'user_id' not in session:
            session['next_url'] = request.url
            return redirect('/sso/dev-login')

        # Otherwise, seed a dev session for convenience
        if 'user_id' not in session:
            dev_user_id = config.get('SSO', 'dev_user_id', fallback='dev_user')
            dev_user_name = config.get('SSO', 'dev_user_name', fallback='개발자')
            dev_department = config.get('SSO', 'dev_department', fallback='개발팀')
            dev_grade = config.get('SSO', 'dev_grade', fallback='과장')

            session['user_id'] = dev_user_id
            session['user_name'] = dev_user_name
            session['department'] = dev_department
            session['grade'] = dev_grade

            # Also provide compatibility aliases
            session['login_id'] = dev_user_id
            session['LoginId'] = dev_user_id
            session['Username'] = dev_user_name
            session['dept_name'] = dev_department
            session['DeptName'] = dev_department
            session['dept_id'] = session.get('dept_id', '')
            session['DeptId'] = session.get('DeptId', '')
        return None

    # Enforce SSO
    if 'user_id' not in session:
        session['next_url'] = request.url
        return redirect('/sso/auth')

    # Optional: token expiry check if stored
    exp_iso = session.get('token_expires')
    if exp_iso:
        try:
            if datetime.now(timezone.utc) > datetime.fromisoformat(exp_iso):
                session.clear()
                session['next_url'] = request.url
                return redirect('/sso/auth')
        except Exception:
            # if parsing fails, continue
            pass

    return None
