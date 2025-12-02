from flask import Blueprint, render_template
from flask_login import current_user
from ..models import Community

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Página inicial do site"""
    communities = Community.query.order_by(Community.name.asc()).all()
    return render_template(
        'main/index.html',
        usuario=current_user,
        communities=communities
    )