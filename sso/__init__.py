from flask import Blueprint

sso_bp = Blueprint('sso', __name__, url_prefix='/sso')

__all__ = [
    'sso_bp'
]

