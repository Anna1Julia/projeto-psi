#Rota responsável por renderizar a página da comunidade e lidar com postagens
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from ..models import db, CommunityPost, Community, CommunityBlock, CommunityPostLike, CommunityPostComment, Usuario

comunidade_bp = Blueprint('comunidade', __name__, url_prefix='/comunidade')

@comunidade_bp.route('/', methods=['GET'])
@login_required
def comunidade():
    # Usa o novo método para obter comunidades acessíveis
    include_filtered = request.args.get('include_filtered', 'false').lower() == 'true'
    comunidades = current_user.get_accessible_communities(include_filtered=include_filtered)
    return render_template('lista_comunidades.html', comunidades=comunidades)

@comunidade_bp.route('/minhascomunidades/', methods=['GET'])
@login_required
def minhas_comunidades():
    """Lista apenas comunidades em que o usuário é membro (dono ou interagiu)."""
    include_filtered = request.args.get('include_filtered', 'false').lower() == 'true'

    # Subconsultas de participação por posts, comentários e likes
    user_post_communities = db.session.query(CommunityPost.community_id).filter(
        CommunityPost.author_id == current_user.id
    )

    user_comment_communities = (db.session.query(CommunityPost.community_id)
        .join(CommunityPostComment, CommunityPostComment.post_id == CommunityPost.id)
        .filter(CommunityPostComment.user_id == current_user.id)
    )

    user_like_communities = (db.session.query(CommunityPost.community_id)
        .join(CommunityPostLike, CommunityPostLike.post_id == CommunityPost.id)
        .filter(CommunityPostLike.user_id == current_user.id)
    )

    # Comunidades bloqueadas pelo usuário (para exclusão)
    blocked_ids = db.session.query(CommunityBlock.community_id).filter(
        CommunityBlock.user_id == current_user.id
    )

    query = Community.query.filter(Community.status == 'active')

    # Participação: dono ou interagiu (post, comentário, like)
    query = query.filter(
        (
            (Community.owner_id == current_user.id) |
            (Community.id.in_(user_post_communities)) |
            (Community.id.in_(user_comment_communities)) |
            (Community.id.in_(user_like_communities))
        )
    )

    # Excluir bloqueadas
    query = query.filter(~Community.id.in_(blocked_ids))

    # Filtragem de conteúdo sensível
    if not include_filtered:
        query = query.filter(Community.is_filtered.is_(False))

    comunidades = query.order_by(Community.created_at.asc()).all()

    return render_template('lista_comunidades.html', comunidades=comunidades)

@comunidade_bp.route('/minhascomuidades/', methods=['GET'])
@login_required
def minhas_comuidades_alias():
    """Alias com a grafia solicitada, redireciona para a rota correta."""
    return redirect(url_for('comunidade.minhas_comunidades', **request.args))

@comunidade_bp.route('/oficial', methods=['GET'])
@login_required
def comunidade_oficial():
    """Redireciona diretamente para a comunidade oficial MemóriaViva"""
    # Buscar comunidade oficial
    comunidade_oficial = Community.query.filter_by(name='MemóriaViva').first()
    
    if not comunidade_oficial:
        flash('Comunidade oficial não encontrada.', 'error')
        return redirect(url_for('comunidade.comunidade'))
    
    # Redirecionar para a comunidade
    return redirect(url_for('comunidade.comunidade_users', community_id=comunidade_oficial.id))

@comunidade_bp.route('/<int:community_id>', methods=['GET', 'POST'])
@login_required
def comunidade_users(community_id):
    comunidade = Community.query.get_or_404(community_id)
    
    # Verifica se o usuário pode acessar a comunidade
    if not comunidade.can_user_access(current_user.id):
        flash('Você não tem permissão para acessar esta comunidade.', 'error')
        return redirect(url_for('comunidade.comunidade'))
    
    # Verifica se a comunidade está bloqueada pelo usuário
    if current_user.is_community_blocked(community_id):
        flash('Esta comunidade está bloqueada para você.', 'error')
        return redirect(url_for('comunidade.comunidade'))

    if request.method == 'POST':
        texto = request.form.get('mensagem')
        if texto:
            # Verificar se o usuário pode postar
            can_post, error_msg = current_user.can_post()
            if not can_post:
                flash(error_msg, 'danger')
                return redirect(url_for('comunidade.comunidade_users', community_id=comunidade.id))
            
            nova_mensagem = CommunityPost(content=texto, author_id=current_user.id, community_id=comunidade.id)
            db.session.add(nova_mensagem)
            db.session.commit()
            return redirect(url_for('comunidade.comunidade_users', community_id=comunidade.id))

    # Filtrar posts: mostrar todos para admin, ocultos apenas para o autor
    query = CommunityPost.query.filter_by(community_id=comunidade.id)
    if not current_user.is_admin:
        # Usuários comuns só veem posts não ocultos ou seus próprios posts ocultos
        from sqlalchemy import or_
        query = query.filter(
            or_(
                CommunityPost.is_hidden == False,
                (CommunityPost.is_hidden == True) & (CommunityPost.author_id == current_user.id)
            )
        )
    mensagens = query.order_by(CommunityPost.created_at.desc()).all()
    return render_template('comunidade.html', comunidade=comunidade, mensagens=mensagens)

@comunidade_bp.route('/<int:community_id>/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(community_id, post_id):
    post = CommunityPost.query.filter_by(id=post_id, community_id=community_id).first_or_404()
    existing = CommunityPostLike.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'liked': False, 'likes_count': CommunityPostLike.query.filter_by(post_id=post.id).count()})
    novo = CommunityPostLike(user_id=current_user.id, post_id=post.id)
    db.session.add(novo)
    db.session.commit()
    return jsonify({'liked': True, 'likes_count': CommunityPostLike.query.filter_by(post_id=post.id).count()})

@comunidade_bp.route('/<int:community_id>/post/<int:post_id>/comment', methods=['POST'])
@login_required
def comment_post(community_id, post_id):
    post = CommunityPost.query.filter_by(id=post_id, community_id=community_id).first_or_404()
    text = request.form.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'message': 'Comentário vazio'}), 400
    comment = CommunityPostComment(user_id=current_user.id, post_id=post.id, text=text)
    db.session.add(comment)
    db.session.commit()
    
    # Importar o helper de formatação de data
    from ..utils.helpers import format_datetime
    
    return jsonify({
        'success': True,
        'comments_count': CommunityPostComment.query.filter_by(post_id=post.id).count(),
        'comment': {
            'id': comment.id,
            'author': current_user.nome,
            'text': comment.text,
            'created_at': format_datetime(comment.created_at, '%d/%m/%Y %H:%M'),
            'created_at_iso': comment.created_at.isoformat(),
            'created_at_ts': int(comment.created_at.timestamp() * 1000)
        }
    })

@comunidade_bp.route('/criar', methods=['GET', 'POST'])
@login_required
def criar_comunidade():
    if request.method == 'POST':
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')

        if nome:
            nova_comunidade = Community(owner_id=current_user.id, name=nome, description=descricao)
            db.session.add(nova_comunidade)
            db.session.commit()
            return redirect(url_for('comunidade.comunidade_users', community_id=nova_comunidade.id))

    return render_template('criar_comunidade.html')

@comunidade_bp.route('/delete/<int:community_id>', methods=['POST'])
@login_required
def delete_community(community_id):
    """Deleta uma comunidade (apenas o criador)"""
    comunidade = Community.query.get_or_404(community_id)
    
    # Verificar se o usuário atual é o dono da comunidade
    if comunidade.owner_id != current_user.id:
        flash('Acesso negado. Apenas o criador da comunidade pode apagá-la.', 'error')
        return redirect(url_for('comunidade.comunidade'))
    
    community_name = comunidade.name
    
    try:
        # Deletar todos os posts relacionados (e seus likes/comentários serão deletados em cascata)
        CommunityPost.query.filter_by(community_id=community_id).delete()
        # Deletar todos os bloqueios relacionados à comunidade
        CommunityBlock.query.filter_by(community_id=community_id).delete()
        # Deletar a comunidade
        db.session.delete(comunidade)
        db.session.commit()
        flash(f'Comunidade "{community_name}" foi apagada com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao apagar comunidade: {str(e)}', 'error')
    
    return redirect(url_for('comunidade.comunidade'))

# Novas rotas para bloqueio e filtragem
@comunidade_bp.route('/block/<int:community_id>', methods=['POST'])
@login_required
def block_community(community_id):
    """Bloqueia uma comunidade para o usuário atual"""
    reason = request.form.get('reason', None)
    
    success, message = current_user.block_community(community_id, reason)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': success, 'message': message})
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('comunidade.comunidade'))

@comunidade_bp.route('/unblock/<int:community_id>', methods=['POST'])
@login_required
def unblock_community(community_id):
    """Remove o bloqueio de uma comunidade"""
    success, message = current_user.unblock_community(community_id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': success, 'message': message})
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('comunidade.comunidade'))

@comunidade_bp.route('/blocked', methods=['GET'])
@login_required
def blocked_communities():
    """Lista todas as comunidades bloqueadas pelo usuário"""
    blocked_communities = current_user.get_blocked_communities()
    return render_template('comunidades_bloqueadas.html', comunidades=blocked_communities)

# Rotas administrativas para gerenciar status das comunidades
@comunidade_bp.route('/admin/block/<int:community_id>', methods=['POST'])
@login_required
def admin_block_community(community_id):
    """Bloqueia uma comunidade (apenas administradores)"""
    if not current_user.is_administrador():
        flash('Acesso negado. Apenas administradores podem realizar esta ação.', 'error')
        return redirect(url_for('comunidade.comunidade'))
    
    comunidade = Community.query.get_or_404(community_id)
    comunidade.status = 'blocked'
    db.session.commit()
    
    flash(f'Comunidade "{comunidade.name}" foi bloqueada.', 'success')
    return redirect(url_for('comunidade.comunidade'))

@comunidade_bp.route('/admin/unblock/<int:community_id>', methods=['POST'])
@login_required
def admin_unblock_community(community_id):
    """Desbloqueia uma comunidade (apenas administradores)"""
    if not current_user.is_administrador():
        flash('Acesso negado. Apenas administradores podem realizar esta ação.', 'error')
        return redirect(url_for('comunidade.comunidade'))
    
    comunidade = Community.query.get_or_404(community_id)
    comunidade.status = 'active'
    db.session.commit()
    
    flash(f'Comunidade "{comunidade.name}" foi desbloqueada.', 'success')
    return redirect(url_for('comunidade.comunidade'))

@comunidade_bp.route('/admin/filter/<int:community_id>', methods=['POST'])
@login_required
def admin_filter_community(community_id):
    """Aplica filtro de conteúdo sensível (apenas administradores)"""
    if not current_user.is_administrador():
        flash('Acesso negado. Apenas administradores podem realizar esta ação.', 'error')
        return redirect(url_for('comunidade.comunidade'))
    
    comunidade = Community.query.get_or_404(community_id)
    reason = request.form.get('reason', 'Conteúdo sensível')
    
    comunidade.is_filtered = True
    comunidade.filter_reason = reason
    db.session.commit()
    
    flash(f'Comunidade "{comunidade.name}" foi marcada como filtrada.', 'success')
    return redirect(url_for('comunidade.comunidade'))

@comunidade_bp.route('/admin/unfilter/<int:community_id>', methods=['POST'])
@login_required
def admin_unfilter_community(community_id):
    """Remove filtro de conteúdo sensível (apenas administradores)"""
    if not current_user.is_administrador():
        flash('Acesso negado. Apenas administradores podem realizar esta ação.', 'error')
        return redirect(url_for('comunidade.comunidade'))
    
    comunidade = Community.query.get_or_404(community_id)
    comunidade.is_filtered = False
    comunidade.filter_reason = None
    db.session.commit()
    
    flash(f'Comunidade "{comunidade.name}" teve o filtro removido.', 'success')
    return redirect(url_for('comunidade.comunidade'))

@comunidade_bp.route('/<int:community_id>/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(community_id, post_id):
    """Excluir post de uma comunidade"""
    from flask import jsonify
    
    post = CommunityPost.query.get_or_404(post_id)
    comunidade = Community.query.get_or_404(community_id)
    
    # Verificar permissão: autor do post, admin, dono da comunidade ou admin específico
    from ..blueprints.users import can_delete_users
    if (current_user.id != post.author_id and not current_user.is_admin 
        and current_user.id != comunidade.owner_id and not can_delete_users()):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Sem permissão'}), 403
        flash('Você não tem permissão para excluir este post.', 'danger')
        return redirect(url_for('comunidade.comunidade_users', community_id=community_id))
    
    try:
        # Deletar comentários associados
        CommunityPostComment.query.filter_by(post_id=post_id).delete()
        
        # Deletar likes associados
        CommunityPostLike.query.filter_by(post_id=post_id).delete()
        
        # Deletar o post
        db.session.delete(post)
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Post excluído'})
        
        flash('Post excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Erro ao excluir post: {str(e)}', 'danger')
    
    return redirect(url_for('comunidade.comunidade_users', community_id=community_id))

@comunidade_bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    """Excluir comentário de um post"""
    from flask import jsonify
    
    comentario = CommunityPostComment.query.get_or_404(comment_id)
    post_id = comentario.post_id
    post = CommunityPost.query.get(post_id)
    comunidade = Community.query.get(post.community_id) if post else None
    
    # Verificar permissão: autor do comentário, admin ou dono da comunidade
    if current_user.id != comentario.user_id and not current_user.is_admin and (not comunidade or current_user.id != comunidade.owner_id):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Sem permissão'}), 403
        flash('Você não tem permissão para excluir este comentário.', 'danger')
        return redirect(url_for('comunidade.comunidade_users', community_id=post.community_id))
    
    try:
        db.session.delete(comentario)
        db.session.commit()
        
        # Contar comentários restantes
        comments_count = CommunityPostComment.query.filter_by(post_id=post_id).count()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Comentário excluído', 'comments_count': comments_count})
        
        flash('Comentário excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(f'Erro ao excluir comentário: {str(e)}', 'danger')
    
    return redirect(url_for('comunidade.comunidade_users', community_id=post.community_id))

@comunidade_bp.route('/<int:community_id>/post/<int:post_id>/hide', methods=['POST'])
@login_required
def hide_post(community_id, post_id):
    """Ocultar post (só admin e o próprio autor veem)"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    post = CommunityPost.query.get_or_404(post_id)
    post.is_hidden = True
    post.hidden_by = current_user.id
    post.hidden_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Post ocultado com sucesso'})

@comunidade_bp.route('/<int:community_id>/post/<int:post_id>/unhide', methods=['POST'])
@login_required
def unhide_post(community_id, post_id):
    """Desocultar post"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    post = CommunityPost.query.get_or_404(post_id)
    post.is_hidden = False
    post.hidden_by = None
    post.hidden_at = None
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Post desocultado com sucesso'})

@comunidade_bp.route('/user/<int:user_id>/ban', methods=['POST'])
@login_required
def ban_user(user_id):
    """Banir usuário permanentemente"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    user = Usuario.query.get_or_404(user_id)
    if user.is_admin:
        return jsonify({'success': False, 'message': 'Não é possível banir um administrador'}), 400
    
    user.is_banned = True
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Usuário {user.nome} foi banido permanentemente'})

@comunidade_bp.route('/user/<int:user_id>/unban', methods=['POST'])
@login_required
def unban_user(user_id):
    """Desbanir usuário"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    user = Usuario.query.get_or_404(user_id)
    user.is_banned = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Usuário {user.nome} foi desbanido'})

@comunidade_bp.route('/user/<int:user_id>/mute', methods=['POST'])
@login_required
def mute_user(user_id):
    """Aplicar castigo (mute temporário) ao usuário"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    user = Usuario.query.get_or_404(user_id)
    if user.is_admin:
        return jsonify({'success': False, 'message': 'Não é possível aplicar castigo a um administrador'}), 400
    
    data = request.get_json() if request.is_json else request.form
    days = int(data.get('days', 1))
    reason = data.get('reason', 'Violação das regras da comunidade')
    
    user.is_muted = True
    user.mute_until = datetime.utcnow() + timedelta(days=days)
    user.mute_reason = reason
    db.session.commit()
    
    from ..utils.helpers import format_datetime
    
    return jsonify({
        'success': True, 
        'message': f'Castigo aplicado a {user.nome} até {format_datetime(user.mute_until, "%d/%m/%Y %H:%M")}'
    })

@comunidade_bp.route('/user/<int:user_id>/unmute', methods=['POST'])
@login_required
def unmute_user(user_id):
    """Remover castigo do usuário"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
    
    user = Usuario.query.get_or_404(user_id)
    user.is_muted = False
    user.mute_until = None
    user.mute_reason = None
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Castigo removido de {user.nome}'})

@comunidade_bp.route('/appeal', methods=['POST'])
@login_required
def appeal_mute():
    """Recurso de castigo (usuário pode apelar)"""
    data = request.get_json() if request.is_json else request.form
    appeal_message = data.get('message', '')
    
    if not current_user.is_currently_muted():
        return jsonify({'success': False, 'message': 'Você não está sob castigo'}), 400
    
    # Criar notificação para todos os admins sobre o recurso
    from ..models import Notification
    admins = Usuario.query.filter_by(is_admin=True).all()
    for admin in admins:
        notification = Notification(
            user_id=admin.id,
            type='appeal',
            title='Recurso de Castigo',
            message=f'O usuário {current_user.nome} está apelando de seu castigo. Motivo do castigo: {current_user.mute_reason or "Não especificado"}. Mensagem do usuário: {appeal_message}',
            link=url_for('users.profile', user_id=current_user.id),
            is_read=False
        )
        db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Recurso enviado. Os administradores serão notificados.'})