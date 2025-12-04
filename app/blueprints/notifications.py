from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Notification
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('/')
@login_required
def list_notifications():
    """Lista todas as notificações do usuário"""
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .limit(50)\
        .all()
    
    return render_template('notifications/list.html', notifications=notifications)

@notifications_bp.route('/unread-count')
@login_required
def unread_count():
    """Retorna o número de notificações não lidas (JSON)"""
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({'count': count})

@notifications_bp.route('/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_as_read(notification_id):
    """Marca uma notificação como lida"""
    notification = Notification.query.get_or_404(notification_id)
    
    # Verificar se a notificação pertence ao usuário
    if notification.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'success': True})

@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_as_read():
    """Marca todas as notificações do usuário como lidas"""
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    return jsonify({'success': True})

@notifications_bp.route('/recent')
@login_required
def recent_notifications():
    """Retorna notificações recentes (JSON) - para dropdown no header"""
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .limit(10)\
        .all()
    
    return jsonify({
        'notifications': [{
            'id': n.id,
            'type': n.type,
            'title': n.title,
            'message': n.message,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat() if n.created_at else None
        } for n in notifications]
    })

