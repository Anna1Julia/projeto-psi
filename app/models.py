from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from .extensions import bcrypt
from werkzeug.security import check_password_hash as werkzeug_check_password_hash

db = SQLAlchemy()

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'tb_users'
    __table_args__ = (
        db.UniqueConstraint('usr_email', name='uq_usuario_email'),
        {'sqlite_autoincrement': True}
    )

    id = db.Column('usr_id', db.Integer, primary_key=True)
    nome = db.Column('usr_name', db.String(255), nullable=False)
    email = db.Column('usr_email', db.String(255), nullable=False, unique=True, index=True)
    _senha_hash = db.Column('usr_password', db.String(255), nullable=False)
    profile_picture = db.Column('usr_profile_picture', db.String(255))
    biografia = db.Column('usr_bio', db.Text)
    role = db.Column('usr_role', db.String(32), default='visitante', nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    criado_em = db.Column('usr_created_at', db.DateTime, default=datetime.utcnow, nullable=False)

    seguidores = db.relationship('Follower', foreign_keys='Follower.follower_id', backref='seguidor', lazy='dynamic')
    seguidos = db.relationship('Follower', foreign_keys='Follower.followed_id', backref='seguido', lazy='dynamic')
    mensagens_enviadas = db.relationship('PrivateMessage', foreign_keys='PrivateMessage.sender_id', backref='sender', lazy='dynamic')
    mensagens_recebidas = db.relationship('PrivateMessage', foreign_keys='PrivateMessage.receiver_id', backref='receiver', lazy='dynamic')
    comentarios = db.relationship('Comment', backref='user', lazy='dynamic')
    likes = db.relationship('Like', backref='user', lazy='dynamic')
    historico_assistido = db.relationship('WatchHistory', backref='user', lazy='dynamic')
    avaliacoes = db.relationship('Rating', back_populates='usuario', lazy='dynamic')

    def __repr__(self):
        return f"<Usuario {self.email}>"

    def is_administrador(self):
        return self.is_admin

    @property
    def senha(self):
        raise AttributeError("Senha não pode ser lida diretamente.")

    @senha.setter
    def senha(self, senha_plaintext):
        self._senha_hash = bcrypt.generate_password_hash(senha_plaintext).decode('utf-8')

    def checar_senha(self, senha_plaintext):
        try:
            if bcrypt.check_password_hash(self._senha_hash, senha_plaintext):
                return True
        except Exception:
            pass
        try:
            return werkzeug_check_password_hash(self._senha_hash, senha_plaintext)
        except Exception:
            return False
    
    # Métodos para gerenciar bloqueios de comunidades
    def block_community(self, community_id, reason=None):
        """Bloqueia uma comunidade para o usuário"""
        from .models import CommunityBlock, Community
        
        # Verifica se já existe um bloqueio
        existing_block = CommunityBlock.query.filter_by(
            user_id=self.id, 
            community_id=community_id
        ).first()
        
        if existing_block:
            return False, "Comunidade já está bloqueada"
        
        # Verifica se a comunidade existe
        community = Community.query.get(community_id)
        if not community:
            return False, "Comunidade não encontrada"
        
        # Cria o bloqueio
        block = CommunityBlock(
            user_id=self.id,
            community_id=community_id,
            reason=reason
        )
        db.session.add(block)
        db.session.commit()
        
        return True, "Comunidade bloqueada com sucesso"
    
    def unblock_community(self, community_id):
        """Remove o bloqueio de uma comunidade"""
        from .models import CommunityBlock
        
        block = CommunityBlock.query.filter_by(
            user_id=self.id, 
            community_id=community_id
        ).first()
        
        if not block:
            return False, "Comunidade não está bloqueada"
        
        db.session.delete(block)
        db.session.commit()
        
        return True, "Bloqueio removido com sucesso"
    
    def is_community_blocked(self, community_id):
        """Verifica se uma comunidade está bloqueada pelo usuário"""
        from .models import CommunityBlock
        
        return CommunityBlock.query.filter_by(
            user_id=self.id, 
            community_id=community_id
        ).first() is not None
    
    def get_blocked_communities(self):
        """Retorna todas as comunidades bloqueadas pelo usuário"""
        from .models import CommunityBlock
        
        blocks = CommunityBlock.query.filter_by(user_id=self.id).all()
        return [block.community for block in blocks]
    
    def get_accessible_communities(self, include_filtered=False):
        """Retorna todas as comunidades acessíveis ao usuário"""
        from sqlalchemy import select
        from .models import Community, CommunityBlock
        
        # Base: somente comunidades ativas
        query = Community.query.filter(Community.status == 'active')
        
        # Excluir comunidades bloqueadas pelo usuário (subconsulta com select())
        blocked_ids_select = select(CommunityBlock.community_id).where(CommunityBlock.user_id == self.id)
        query = query.filter(~Community.id.in_(blocked_ids_select))
        
        # Filtrar conteúdo sensível, se aplicável
        if not include_filtered:
            query = query.filter(Community.is_filtered.is_(False))
        
        return query.order_by(Community.created_at.asc()).all()
    
    

class Follower(db.Model):
    __tablename__ = 'tb_followers'

    follower_id = db.Column('fol_follower_id', db.Integer, db.ForeignKey('tb_users.usr_id'), primary_key=True)
    followed_id = db.Column('fol_followed_id', db.Integer, db.ForeignKey('tb_users.usr_id'), primary_key=True)
    followed_at = db.Column('fol_followed_at', db.DateTime, default=datetime.utcnow, nullable=False)

class PrivateMessage(db.Model):
    __tablename__ = 'tb_private_messages'

    id = db.Column('msg_id', db.Integer, primary_key=True)
    sender_id = db.Column('msg_sender_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    receiver_id = db.Column('msg_receiver_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    text = db.Column('msg_text', db.Text, nullable=False)
    sent_at = db.Column('msg_sent_at', db.DateTime, default=datetime.utcnow, nullable=False)
    is_read = db.Column('msg_is_read', db.Boolean, default=False, nullable=False)

#Classe para que as mensagens fiquem visiveis para todos os usuários
class CommunityPost(db.Model):
    __tablename__ = 'tb_community_posts'

    id = db.Column('post_id', db.Integer, primary_key=True)
    author_id = db.Column('post_author_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    community_id = db.Column('post_community_id', db.Integer, db.ForeignKey('tb_communities.com_id'), nullable=False)
    content = db.Column('post_content', db.Text, nullable=False)
    created_at = db.Column('post_created_at', db.DateTime, default=datetime.utcnow, nullable=False)

    usuario = db.relationship('Usuario', backref='community_posts')
    comunidade = db.relationship('Community', back_populates='posts')

    # Helpers
    def likes_count(self):
        return CommunityPostLike.query.filter_by(post_id=self.id).count()

    def comments_count(self):
        return CommunityPostComment.query.filter_by(post_id=self.id).count()

    def get_comments(self):
        return (CommunityPostComment.query
                .filter_by(post_id=self.id)
                .order_by(CommunityPostComment.created_at.desc())
                .all())



#Classe para comunidades criadas por usuários 

class Community(db.Model):
    __tablename__ = 'tb_communities'

    id = db.Column('com_id', db.Integer, primary_key=True)
    owner_id = db.Column('com_owner_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    name = db.Column('com_name', db.String(255), nullable=False)  # nome da comunidade
    description = db.Column('com_description', db.Text)
    status = db.Column('com_status', db.String(20), default='active', nullable=False)  # active, blocked, private
    is_filtered = db.Column('com_is_filtered', db.Boolean, default=False, nullable=False)  # para conteúdo sensível
    filter_reason = db.Column('com_filter_reason', db.String(255))  # motivo do filtro
    created_at = db.Column('com_created_at', db.DateTime, default=datetime.utcnow, nullable=False)

    owner = db.relationship('Usuario', backref='owned_communities')
    posts = db.relationship('CommunityPost', back_populates='comunidade', lazy='dynamic')
    blocks = db.relationship('CommunityBlock', backref='community', lazy='dynamic')

    def is_blocked(self):
        """Verifica se a comunidade está bloqueada"""
        return self.status == 'blocked'
    
    def is_private(self):
        """Verifica se a comunidade é privada"""
        return self.status == 'private'
    
    def can_user_access(self, user_id):
        """Verifica se um usuário pode acessar a comunidade"""
        if self.is_blocked():
            return False
        if self.is_private() and self.owner_id != user_id:
            return False
        return True


#Classe para gerenciar bloqueios de comunidades por usuários
class CommunityBlock(db.Model):
    __tablename__ = 'tb_community_blocks'

    id = db.Column('blk_id', db.Integer, primary_key=True)
    user_id = db.Column('blk_user_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    community_id = db.Column('blk_community_id', db.Integer, db.ForeignKey('tb_communities.com_id'), nullable=False)
    reason = db.Column('blk_reason', db.String(255))  # motivo do bloqueio
    created_at = db.Column('blk_created_at', db.DateTime, default=datetime.utcnow, server_default=db.func.current_timestamp(), nullable=False)

    user = db.relationship('Usuario', backref='blocked_communities')

    def __repr__(self):
        return f"<CommunityBlock {self.user_id} -> {self.community_id}>"

class Comment(db.Model):
    __tablename__ = 'tb_comments'

    id = db.Column('cmt_id', db.Integer, primary_key=True)
    user_id = db.Column('cmt_user_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    content_id = db.Column('cmt_content_id', db.Integer, db.ForeignKey('tb_contents.cnt_id'), nullable=False)
    text = db.Column('cmt_text', db.Text, nullable=False)
    created_at = db.Column('cmt_created_at', db.DateTime, default=datetime.utcnow, nullable=False)

class Like(db.Model):
    __tablename__ = 'tb_likes'

    id = db.Column('lik_id', db.Integer, primary_key=True)
    user_id = db.Column('lik_user_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    content_id = db.Column('lik_content_id', db.Integer, db.ForeignKey('tb_contents.cnt_id'), nullable=False)
    created_at = db.Column('lik_created_at', db.DateTime, default=datetime.utcnow, nullable=False)

class CommunityPostLike(db.Model):
    __tablename__ = 'tb_community_post_likes'

    id = db.Column('cpl_id', db.Integer, primary_key=True)
    user_id = db.Column('cpl_user_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    post_id = db.Column('cpl_post_id', db.Integer, db.ForeignKey('tb_community_posts.post_id'), nullable=False)
    created_at = db.Column('cpl_created_at', db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship helpers for rendering
    user = db.relationship('Usuario')
    post = db.relationship('CommunityPost')

class CommunityPostComment(db.Model):
    __tablename__ = 'tb_community_post_comments'

    id = db.Column('cpc_id', db.Integer, primary_key=True)
    user_id = db.Column('cpc_user_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    post_id = db.Column('cpc_post_id', db.Integer, db.ForeignKey('tb_community_posts.post_id'), nullable=False)
    text = db.Column('cpc_text', db.Text, nullable=False)
    created_at = db.Column('cpc_created_at', db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship helpers for rendering
    user = db.relationship('Usuario')
    post = db.relationship('CommunityPost')

class WatchHistory(db.Model):
    __tablename__ = 'tb_watch_history'

    id = db.Column('wht_id', db.Integer, primary_key=True)
    user_id = db.Column('wht_user_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    content_id = db.Column('wht_content_id', db.Integer, db.ForeignKey('tb_contents.cnt_id'), nullable=False)
    last_watched = db.Column('wht_last_watched', db.DateTime, default=datetime.utcnow, nullable=False)
    progress = db.Column('wht_progress', db.Float, nullable=False)

class Rating(db.Model):
    __tablename__ = 'tb_ratings'

    id = db.Column('rat_id', db.Integer, primary_key=True)
    user_id = db.Column('rat_user_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    content_id = db.Column('rat_content_id', db.Integer, db.ForeignKey('tb_contents.cnt_id'), nullable=False)
    rating = db.Column('rat_rating', db.Integer, nullable=False)  # 1-5 estrelas
    review = db.Column('rat_review', db.Text)  # Comentário opcional
    created_at = db.Column('rat_created_at', db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relacionamento com usuário
    usuario = db.relationship('Usuario', back_populates='avaliacoes', lazy=True)

class Content(db.Model):
    __tablename__ = 'tb_contents'

    id = db.Column('cnt_id', db.Integer, primary_key=True)
    title = db.Column('cnt_title', db.String(255), nullable=False)
    description = db.Column('cnt_description', db.Text)
    type = db.Column('cnt_type', db.String(50), nullable=False)  # livro, manifesto, relato etc.
    release_date = db.Column('cnt_release_date', db.Date)
    thumbnail = db.Column('cnt_thumbnail', db.String(255))
    url = db.Column('cnt_url', db.String(255))
    file_path = db.Column('cnt_file_path', db.String(500))  # caminho do arquivo PDF/EPUB
    file_type = db.Column('cnt_file_type', db.String(10))  # pdf, epub, etc.
    created_at = db.Column('cnt_created_at', db.DateTime, default=datetime.utcnow, nullable=False)
    views_count = db.Column('cnt_views_count', db.Integer, default=0, nullable=False)

    # 🔹 Adiciona referência ao autor/criador
    user_id = db.Column('cnt_user_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)

    # 🔹 Relacionamentos
    autor = db.relationship('Usuario', backref=db.backref('conteudos', lazy='dynamic'))
    comentarios = db.relationship('Comment', backref='content', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='content', lazy='dynamic', cascade='all, delete-orphan')
    historico_assistido = db.relationship('WatchHistory', backref='content', lazy='dynamic', cascade='all, delete-orphan')
    avaliacoes = db.relationship('Rating', backref='content', lazy='dynamic', cascade='all, delete-orphan')
    categorias = db.relationship('ContentCategory', backref='content', lazy='dynamic', cascade='all, delete-orphan')
    

class Category(db.Model):
    __tablename__ = 'tb_categories'

    id = db.Column('cat_id', db.Integer, primary_key=True)
    name = db.Column('cat_name', db.String(255), nullable=False)

    # Relacionamento
    conteudos = db.relationship('ContentCategory', backref='category', lazy='dynamic')


class Media(db.Model):
    __tablename__ = 'tb_media'

    id = db.Column('med_id', db.Integer, primary_key=True)
    tipo = db.Column('med_type', db.String(20), nullable=False)  # imagem, áudio, vídeo
    caminho_arquivo = db.Column('med_path', db.String(500), nullable=False)
    descricao = db.Column('med_description', db.Text)


class Event(db.Model):
    __tablename__ = 'tb_events'

    id = db.Column('evt_id', db.Integer, primary_key=True)
    titulo = db.Column('evt_title', db.String(255), nullable=False)
    descricao = db.Column('evt_description', db.Text)
    data_evento = db.Column('evt_date', db.Date)
    local = db.Column('evt_location', db.String(255))
    imagem = db.Column('evt_image', db.String(500))


class Timeline(db.Model):
    __tablename__ = 'tb_timeline'

    id = db.Column('tl_id', db.Integer, primary_key=True)
    ano = db.Column('tl_year', db.Integer, nullable=False)
    titulo = db.Column('tl_title', db.String(255), nullable=False)
    descricao = db.Column('tl_description', db.Text)
    imagem = db.Column('tl_image', db.String(500))
    created_at = db.Column('tl_created_at', db.DateTime, default=datetime.utcnow, nullable=False)

class ContentCategory(db.Model):
    __tablename__ = 'tb_content_categories'

    content_id = db.Column('cct_content_id', db.Integer, db.ForeignKey('tb_contents.cnt_id'), primary_key=True)
    category_id = db.Column('cct_category_id', db.Integer, db.ForeignKey('tb_categories.cat_id'), primary_key=True)

class Report(db.Model):
    __tablename__ = 'tb_reports'

    id = db.Column('rpt_id', db.Integer, primary_key=True)
    reporter_id = db.Column('rpt_reporter_id', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=False)
    reported_type = db.Column('rpt_type', db.String(50), nullable=False)  # 'post', 'content', 'user', 'comment', 'community'
    reported_id = db.Column('rpt_reported_id', db.Integer, nullable=False)  # ID do item denunciado
    reason = db.Column('rpt_reason', db.String(100), nullable=False)  # 'spam', 'inappropriate', 'harassment', 'copyright', 'other'
    description = db.Column('rpt_description', db.Text)  # Descrição detalhada
    status = db.Column('rpt_status', db.String(20), default='pending', nullable=False)  # 'pending', 'reviewed', 'resolved', 'dismissed'
    reviewed_by = db.Column('rpt_reviewed_by', db.Integer, db.ForeignKey('tb_users.usr_id'), nullable=True)
    reviewed_at = db.Column('rpt_reviewed_at', db.DateTime, nullable=True)
    admin_notes = db.Column('rpt_admin_notes', db.Text)  # Notas do administrador
    created_at = db.Column('rpt_created_at', db.DateTime, default=datetime.utcnow, nullable=False)

    reporter = db.relationship('Usuario', foreign_keys=[reporter_id], backref='reports_made')
    reviewer = db.relationship('Usuario', foreign_keys=[reviewed_by], backref='reports_reviewed')

    def __repr__(self):
        return f"<Report {self.id}: {self.reported_type}:{self.reported_id} by {self.reporter_id}>"