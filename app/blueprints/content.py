from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from ..models import Content, Rating, db, Category, ContentCategory
import os
from werkzeug.utils import secure_filename
import uuid

# Blueprint corretamente nomeado
content_bp = Blueprint('content', __name__, url_prefix='/content')


# LISTAR CONTEÚDOS
@content_bp.route('/')
def list_content():
    """Lista todo o conteúdo disponível"""
    contents = Content.query.all()

    from ..utils.helpers import extract_youtube_id, youtube_thumbnail_url, youtube_embed_url

    return render_template(
        'content/list.html',
        contents=contents,
        extract_youtube_id=extract_youtube_id,
        youtube_thumbnail_url=youtube_thumbnail_url,
        youtube_embed_url=youtube_embed_url,
    )



# BUSCAR CONTEÚDOS

@content_bp.route('/buscar', methods=['GET'])
@login_required
def buscar_obra():
    termo = (request.args.get('q') or '').strip()
    category_id = request.args.get('category_id', type=int)

    query = Content.query
    if termo:
        query = query.filter(
            db.or_(
                Content.title.ilike(f'%{termo}%'),
                Content.description.ilike(f'%{termo}%')
            )
        )
    if category_id:
        query = query.join(ContentCategory, Content.id == ContentCategory.content_id)
        query = query.filter(ContentCategory.category_id == category_id)

    resultados = query.order_by(Content.created_at.desc()).all() if (termo or category_id) else []
    categorias = Category.query.order_by(Category.name.asc()).all()

    return render_template(
        'buscar.html',
        resultados=resultados,
        termo=termo,
        categorias=categorias,
        selected_category_id=category_id
    )



# VISUALIZAR CONTEÚDO

@content_bp.route('/<int:content_id>')
def view_content(content_id):
    """Visualiza um conteúdo específico"""
    from sqlalchemy import func
    content = Content.query.get_or_404(content_id)

    ratings = Rating.query.filter_by(content_id=content_id).order_by(Rating.created_at.desc()).all()
    avg_rating = db.session.query(func.avg(Rating.rating)).filter_by(content_id=content_id).scalar()
    total_ratings = len(ratings)

    user_rating = None
    if current_user.is_authenticated:
        user_rating = Rating.query.filter_by(
            user_id=current_user.id,
            content_id=content_id
        ).first()

    from ..utils.helpers import extract_youtube_id, youtube_thumbnail_url, youtube_embed_url

    return render_template(
        'content/view.html',
        content=content,
        ratings=ratings,
        avg_rating=avg_rating,
        total_ratings=total_ratings,
        user_rating=user_rating,
        extract_youtube_id=extract_youtube_id,
        youtube_thumbnail_url=youtube_thumbnail_url,
        youtube_embed_url=youtube_embed_url,
    )



# CRIAR CONTEÚDO

@content_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_content():
    """Cria novo conteúdo"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        content_type = request.form.get('type')
        url = request.form.get('url')
        thumbnail = request.form.get('thumbnail')
        release_date = request.form.get('release_date')

        allowed_types = ['artigo', 'relato', 'entrevista', 'foto']
        if content_type not in allowed_types:
            flash('Tipo de conteúdo inválido.', 'danger')
            return render_template('content/create.html')

        has_file = request.files.get('file') and request.files.get('file').filename != ''
        has_url = url and url.strip() != ''

        if not has_file and not has_url:
            flash('É obrigatório fornecer um arquivo ou um link.', 'danger')
            return render_template('content/create.html')

        relative_path = None
        file_ext = None
        file = request.files.get('file')

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            ALLOWED_FILE_EXTS = ['pdf', 'epub', 'jpg', 'jpeg', 'png', 'webp']
            if file_ext not in ALLOWED_FILE_EXTS:
                flash('Formato de arquivo não permitido.', 'danger')
                return render_template('content/create.html')

            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'obras')
            os.makedirs(upload_dir, exist_ok=True)

            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            file_path = os.path.join(upload_dir, unique_filename)
            file.save(file_path)
            relative_path = f"uploads/obras/{unique_filename}"

        if not thumbnail and url:
            from ..utils.helpers import extract_youtube_id, youtube_thumbnail_url
            video_id = extract_youtube_id(url)
            if video_id:
                thumbnail = youtube_thumbnail_url(video_id, quality='maxresdefault')

        from ..utils.helpers import parse_date
        release_date_obj = parse_date(release_date)

        new_content = Content(
            title=title,
            description=description,
            type=content_type,
            url=url,
            thumbnail=thumbnail,
            release_date=release_date_obj,
            file_path=relative_path,
            file_type=file_ext,
            user_id=current_user.id
        )

        db.session.add(new_content)
        db.session.commit()

        flash('Conteúdo criado com sucesso!', 'success')
        return redirect(url_for('content.list_content'))

    return render_template('content/create.html')

@content_bp.route('/edit/<int:content_id>', methods=['GET', 'POST'])
@login_required
def edit_content(content_id):
    """Edita o conteúdo e gerencia capa permanentemente"""
    content = Content.query.get_or_404(content_id)

    if request.method == 'POST':
        from ..utils.helpers import parse_date

        content.title = request.form.get('title')
        content.description = request.form.get('description')
        content.url = request.form.get('url')
        content.type = request.form.get('type')

        release_date = request.form.get('release_date')
        content.release_date = parse_date(release_date) if release_date else None

        remove_thumbnail = request.form.get('remove_thumbnail') == 'true'
        thumbnail_file = request.files.get('thumbnail_file')
        thumbnail_url = request.form.get('thumbnail')

        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'thumbnails')
        os.makedirs(upload_dir, exist_ok=True)

        # REMOVER CAPA ANTIGA PERMANENTEMENTE
        if remove_thumbnail:
            if content.thumbnail and content.thumbnail.startswith('uploads/'):
                full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', content.thumbnail)
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                        print(f"Capa removida: {full_path}")
                    except Exception as e:
                        print(f"Erro ao remover capa: {e}")
            content.thumbnail = None

        #  NOVO UPLOAD
        elif thumbnail_file and thumbnail_file.filename:
            filename = secure_filename(thumbnail_file.filename)
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(upload_dir, unique_name)
            thumbnail_file.save(save_path)
            content.thumbnail = f"uploads/thumbnails/{unique_name}"

        #  APENAS MUDAR URL MANUAL
        elif thumbnail_url:
            content.thumbnail = thumbnail_url

        try:
            db.session.commit()
            flash("Conteúdo atualizado com sucesso!", "success")
            return jsonify(success=True, new_thumbnail_url=content.thumbnail or url_for('static', filename='img/default_cover.png'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao salvar alterações: {e}")
            return jsonify(success=False, error=str(e)), 500

    return render_template('content/edit.html', content=content)

# DOWNLOAD
@content_bp.route('/<int:content_id>/download')
def download_content(content_id):
    """Permite o download do arquivo do conteúdo"""
    content = Content.query.get_or_404(content_id)

    if not content.file_path:
        flash('Este conteúdo não possui arquivo para download.', 'warning')
        return redirect(url_for('content.view_content', content_id=content_id))

    file_full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', content.file_path)

    if not os.path.exists(file_full_path):
        flash('Arquivo não encontrado.', 'danger')
        return redirect(url_for('content.view_content', content_id=content_id))

    return send_file(file_full_path, as_attachment=True, download_name=os.path.basename(file_full_path))


# AVALIAR CONTEÚDO (RATE)
@content_bp.route('/<int:content_id>/rate', methods=['POST'])
@login_required
def rate_content(content_id):
    """Registra ou atualiza a avaliação de um conteúdo"""
    rating_value = request.form.get('rating', type=int)
    if not rating_value or rating_value < 1 or rating_value > 5:
        flash('Avaliação inválida.', 'danger')
        return redirect(url_for('content.view_content', content_id=content_id))

    existing = Rating.query.filter_by(user_id=current_user.id, content_id=content_id).first()
    if existing:
        existing.rating = rating_value
    else:
        db.session.add(Rating(user_id=current_user.id, content_id=content_id, rating=rating_value))

    db.session.commit()
    flash('Avaliação registrada com sucesso!', 'success')
    return redirect(url_for('content.view_content', content_id=content_id))


# DELETAR CONTEÚDO
@content_bp.route('/<int:content_id>/delete', methods=['POST'])
@login_required
def delete_content(content_id):
    """Deleta um conteúdo"""
    from ..blueprints.users import can_delete_users
    from ..models import Usuario
    
    content = Content.query.get_or_404(content_id)

    # Permitir deletar se for o dono do conteúdo
    is_owner = content.user_id == current_user.id

    # Admin geral pode deletar conteúdos de usuários comuns (não-admin)
    owner_user = content.autor or Usuario.query.get(content.user_id)
    is_target_common_user = owner_user is None or not owner_user.is_administrador()
    can_admin_delete = current_user.is_administrador() and is_target_common_user

    # Admin específico via email ainda mantém permissão total
    if not (is_owner or can_admin_delete or can_delete_users()):
        flash("Você não tem permissão para excluir este conteúdo.", "danger")
        return redirect(url_for('content.view_content', content_id=content_id))

    try:
        if content.file_path:
            file_full_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', content.file_path)
            if os.path.exists(file_full_path):
                os.remove(file_full_path)

        if content.thumbnail and content.thumbnail.startswith('uploads/'):
            thumb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', content.thumbnail)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

        db.session.delete(content)
        db.session.commit()
        flash('Conteúdo deletado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar conteúdo: {str(e)}', 'danger')

    return redirect(url_for('content.list_content'))

# REMOVER AVALIAÇÃO (UNRATE)
@content_bp.route('/remove_rating/<int:rating_id>', methods=['POST'])
@login_required
def remove_rating(rating_id):
    """Remove uma avaliação existente"""
    rating = Rating.query.get_or_404(rating_id)

    # Garante que o usuário só possa remover a própria avaliação
    if rating.user_id != current_user.id:
        flash('Você não tem permissão para remover esta avaliação.', 'danger')
        return redirect(url_for('content.view_content', content_id=rating.content_id))

    try:
        db.session.delete(rating)
        db.session.commit()
        flash('Avaliação removida com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover avaliação: {str(e)}', 'danger')

    return redirect(url_for('content.view_content', content_id=rating.content_id))
