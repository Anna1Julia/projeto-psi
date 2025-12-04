from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.models import db, Report, Usuario, CommunityPost, Content, CommunityPostComment, Notification
from datetime import datetime

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/create', methods=['POST'])
@login_required
def create_report():
    """Cria uma nova denúncia"""
    data = request.get_json() if request.is_json else request.form
    
    reported_type = data.get('reported_type')
    reported_id = data.get('reported_id')
    reason = data.get('reason')
    description = data.get('description', '')
    
    # Validação
    if not all([reported_type, reported_id, reason]):
        if request.is_json:
            return jsonify({'success': False, 'message': 'Campos obrigatórios faltando'}), 400
        flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
        return redirect(request.referrer or url_for('main.index'))
    
    # Verificar se já existe uma denúncia pendente do mesmo usuário para o mesmo item
    existing = Report.query.filter_by(
        reporter_id=current_user.id,
        reported_type=reported_type,
        reported_id=reported_id,
        status='pending'
    ).first()
    
    if existing:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Você já denunciou este item'}), 400
        flash('Você já denunciou este item anteriormente.', 'warning')
        return redirect(request.referrer or url_for('main.index'))
    
    # Verificar se o item denunciado existe
    if reported_type == 'post':
        item = CommunityPost.query.get(reported_id)
    elif reported_type == 'content':
        item = Content.query.get(reported_id)
    elif reported_type == 'user':
        item = Usuario.query.get(reported_id)
    elif reported_type == 'comment':
        item = CommunityPostComment.query.get(reported_id)
    elif reported_type == 'community':
        from app.models import Community
        item = Community.query.get(reported_id)
    else:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Tipo de denúncia inválido'}), 400
        flash('Tipo de denúncia inválido.', 'danger')
        return redirect(request.referrer or url_for('main.index'))
    
    if not item:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Item não encontrado'}), 404
        flash('Item não encontrado.', 'danger')
        return redirect(request.referrer or url_for('main.index'))
    
    # Criar denúncia
    report = Report(
        reporter_id=current_user.id,
        reported_type=reported_type,
        reported_id=reported_id,
        reason=reason,
        description=description,
        status='pending'
    )
    
    db.session.add(report)
    db.session.flush()  # Para obter o ID da denúncia
    
    # Criar notificações para todos os administradores
    admins = Usuario.query.filter_by(is_admin=True).all()
    for admin in admins:
        # Criar mensagem descritiva
        tipo_nome = {
            'post': 'Post',
            'content': 'Conteúdo',
            'user': 'Usuário',
            'comment': 'Comentário',
            'community': 'Comunidade'
        }.get(reported_type, reported_type.title())
        
        motivo_nome = {
            'spam': 'Spam',
            'inappropriate': 'Conteúdo Inadequado',
            'harassment': 'Assédio',
            'copyright': 'Violação de Direitos Autorais',
            'other': 'Outro'
        }.get(reason, reason.title())
        
        title = f"Nova Denúncia: {tipo_nome}"
        message = f"O usuário {current_user.nome} denunciou um {tipo_nome.lower()} (ID: {reported_id}). Motivo: {motivo_nome}."
        if description:
            message += f" Descrição: {description[:100]}{'...' if len(description) > 100 else ''}"
        
        notification = Notification(
            user_id=admin.id,
            type='report',
            title=title,
            message=message,
            link=url_for('reports.view_report', report_id=report.id),
            is_read=False
        )
        db.session.add(notification)
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Denúncia enviada com sucesso'})
    
    flash('Denúncia enviada com sucesso. Nossa equipe irá analisar.', 'success')
    return redirect(request.referrer or url_for('main.index'))

@reports_bp.route('/list')
@login_required
def list_reports():
    """Lista todas as denúncias (apenas para administradores)"""
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem ver denúncias.', 'danger')
        return redirect(url_for('main.index'))
    
    status_filter = request.args.get('status', 'all')
    type_filter = request.args.get('type', 'all')
    
    query = Report.query.order_by(Report.created_at.desc())
    
    if status_filter != 'all':
        query = query.filter(Report.status == status_filter)
    
    if type_filter != 'all':
        query = query.filter(Report.reported_type == type_filter)
    
    reports = query.all()
    
    # Adicionar informações dos itens denunciados
    for report in reports:
        if report.reported_type == 'post':
            report.reported_item = CommunityPost.query.get(report.reported_id)
        elif report.reported_type == 'content':
            report.reported_item = Content.query.get(report.reported_id)
        elif report.reported_type == 'user':
            report.reported_item = Usuario.query.get(report.reported_id)
        elif report.reported_type == 'comment':
            report.reported_item = CommunityPostComment.query.get(report.reported_id)
        elif report.reported_type == 'community':
            from app.models import Community
            report.reported_item = Community.query.get(report.reported_id)
    
    return render_template('reports/list.html', reports=reports, status_filter=status_filter, type_filter=type_filter)

@reports_bp.route('/<int:report_id>/review', methods=['POST'])
@login_required
def review_report(report_id):
    """Revisa uma denúncia (apenas para administradores)"""
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.index'))
    
    report = Report.query.get_or_404(report_id)
    action = request.form.get('action')  # 'resolve', 'dismiss'
    admin_notes = request.form.get('admin_notes', '')
    
    if action == 'resolve':
        report.status = 'resolved'
    elif action == 'dismiss':
        report.status = 'dismissed'
    else:
        flash('Ação inválida.', 'danger')
        return redirect(url_for('reports.list_reports'))
    
    report.reviewed_by = current_user.id
    report.reviewed_at = datetime.utcnow()
    report.admin_notes = admin_notes
    
    db.session.commit()
    
    flash(f'Denúncia {action} com sucesso.', 'success')
    return redirect(url_for('reports.list_reports'))

@reports_bp.route('/<int:report_id>/view')
@login_required
def view_report(report_id):
    """Visualiza detalhes de uma denúncia (apenas para administradores)"""
    if not current_user.is_admin:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('main.index'))
    
    report = Report.query.get_or_404(report_id)
    
    # Buscar o item denunciado
    reported_item = None
    if report.reported_type == 'post':
        reported_item = CommunityPost.query.get(report.reported_id)
    elif report.reported_type == 'content':
        reported_item = Content.query.get(report.reported_id)
    elif report.reported_type == 'user':
        reported_item = Usuario.query.get(report.reported_id)
    elif report.reported_type == 'comment':
        reported_item = CommunityPostComment.query.get(report.reported_id)
    elif report.reported_type == 'community':
        from app.models import Community
        reported_item = Community.query.get(report.reported_id)
    
    return render_template('reports/view.html', report=report, reported_item=reported_item)

