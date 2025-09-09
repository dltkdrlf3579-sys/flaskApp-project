import uuid
from datetime import datetime, timezone
import configparser

from flask import session


class SSOAuthHandler:
    """OIDC-like SSO helper using static IdP certificate and POSTed id_token.

    - Generates auth URL with response_mode=form_post, response_type=id_token.
    - Validates id_token (RS256) using configured IdP certificate.
    - Stores nonce/state in session for CSRF protection.
    """

    def __init__(self, app=None):
        self.app = app
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding='utf-8')
        self.cert = None

    def init_app(self, app):
        self.app = app
        self._load_certificate()

    def _load_certificate(self):
        """Load IdP certificate once if SSO is enabled."""
        sso_enabled = self.config.getboolean('SSO', 'sso_enabled', fallback=False)
        cert_enabled = self.config.getboolean('SSO', 'cert_enabled', fallback=False)
        if not (sso_enabled and cert_enabled):
            return

        cert_path = self.config.get('SSO', 'cert_file_path', fallback='cert/idp.cer')
        try:
            # Lazy import cryptography to avoid hard dependency at import time
            from cryptography import x509  # type: ignore
            from cryptography.hazmat.backends import default_backend  # type: ignore
            with open(cert_path, 'rb') as f:
                cert_data = f.read()
            # Try PEM first, then DER
            try:
                self.cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            except ValueError:
                self.cert = x509.load_der_x509_certificate(cert_data, default_backend())
        except Exception:
            # Certificate not available; validation will fail later if needed
            self.cert = None

    def generate_auth_url(self):
        """Build IdP authorization URL and store nonce/state in session."""
        # If SSO is disabled, just send home
        if not self.config.getboolean('SSO', 'sso_enabled', fallback=False):
            return '/'

        nonce = str(uuid.uuid4())
        state = str(uuid.uuid4())

        session['sso_nonce'] = nonce
        session['sso_state'] = state
        session['sso_timestamp'] = datetime.now(timezone.utc).isoformat()

        # Read config
        client_id = self.config.get('SSO', 'idp_client_id', fallback=self.app.config.get('SSO_CLIENT_ID', ''))
        redirect_uri = self.config.get('SSO', 'sp_redirect_url', fallback=self.app.config.get('SSO_REDIRECT_URI', ''))
        entity_id = self.config.get('SSO', 'idp_entity_id', fallback='')

        # Placeholder/misconfiguration guard: avoid redirecting to example URLs from dev
        if (not entity_id or 'example' in entity_id) or (not redirect_uri or 'example' in redirect_uri):
            # Prefer simulated flow if enabled; otherwise show not-configured page
            simulate = self.config.getboolean('SSO', 'dev_simulate_flow', fallback=False)
            return '/sso/dev-login' if simulate else '/sso/not-configured'

        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_mode': 'form_post',
            'response_type': 'id_token',
            'scope': 'openid profile email',
            'nonce': nonce,
            'state': state,
        }
        # Build query string without encoding (per provided sample)
        query = '&'.join([f"{k}={v}" for k, v in params.items() if v])
        return f"{entity_id}?{query}"

    def validate_token(self, id_token: str):
        """Validate RS256 JWT and return claims.

        Enforces signature, exp. Optionally enforces audience.
        """
        if not id_token:
            raise ValueError('Missing id_token')

        if not self.cert:
            raise ValueError('IdP certificate not loaded (install cryptography and configure cert_file_path)')

        public_key = self.cert.public_key()

        audience = self.config.get('SSO', 'idp_client_id', fallback=self.app.config.get('SSO_CLIENT_ID'))

        try:
            # Lazy import PyJWT to avoid hard dependency at import time
            import jwt  # type: ignore
            decoded = jwt.decode(
                id_token,
                public_key,
                algorithms=['RS256'],
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'verify_aud': True if audience else False,
                    # OIDC implicit may not include iat/nonce depending on IdP, keep relaxed
                },
                audience=audience if audience else None,
            )
        except Exception as e:  # handle import or jwt errors uniformly
            try:
                from jwt import ExpiredSignatureError, InvalidTokenError  # type: ignore
            except Exception:
                raise ValueError('PyJWT not installed. Please install package "PyJWT"') from e
            if isinstance(e, ExpiredSignatureError):
                raise ValueError('Token has expired') from e
            if isinstance(e, InvalidTokenError):
                raise ValueError(f'Invalid token: {str(e)}') from e
            # Fallback
            raise ValueError('Token has expired') from e

        # Optional nonce check
        expected_nonce = session.get('sso_nonce')
        if expected_nonce and decoded.get('nonce') and decoded.get('nonce') != expected_nonce:
            raise ValueError('Invalid nonce')

        return decoded
