from flask import render_template
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import func
from ..models import db, Usuario, Content, Community, Rating
from . import dashboard_bp


@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard principal com estatísticas e gráficos"""
    
    # Estatísticas gerais
    total_usuarios = Usuario.query.count()
    total_obras = Content.query.count()
    total_comunidades = Community.query.count()
    total_avaliacoes = Rating.query.count()
    
    # Últimos 5 itens adicionados (obras/conteúdos)
    ultimos_itens = Content.query.order_by(Content.created_at.desc()).limit(5).all()
    
    # Dados para gráfico de barras - novos itens por mês (últimos 12 meses)
    agora = datetime.utcnow()
    meses_dados = []
    valores_dados = []
    
    for i in range(11, -1, -1):  # Últimos 12 meses
        # Calcula o primeiro dia do mês há i meses atrás
        if i == 0:
            # Mês atual
            data_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora
        else:
            # Meses anteriores - calcula ano e mês
            target_month = agora.month - i
            target_year = agora.year
            
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            
            data_inicio = datetime(target_year, target_month, 1, 0, 0, 0)
            
            # Último dia do mês
            if target_month == 12:
                data_fim = datetime(target_year + 1, 1, 1, 23, 59, 59) - timedelta(days=1)
            else:
                data_fim = datetime(target_year, target_month + 1, 1, 23, 59, 59) - timedelta(days=1)
        
        count = Content.query.filter(
            Content.created_at >= data_inicio,
            Content.created_at <= data_fim
        ).count()
        
        meses_dados.append(data_inicio.strftime('%b/%Y'))
        valores_dados.append(count)
    
    # Dados para gráfico de pizza - proporção por tipo de conteúdo
    tipos_conteudo = db.session.query(
        Content.type,
        func.count(Content.id).label('count')
    ).group_by(Content.type).all()
    
    tipos_labels = [tipo[0] if tipo[0] else 'Sem tipo' for tipo in tipos_conteudo]
    tipos_valores = [tipo[1] for tipo in tipos_conteudo]
    
    # Se não houver tipos, criar dados vazios para evitar erro no gráfico
    if not tipos_labels:
        tipos_labels = ['Sem conteúdo']
        tipos_valores = [0]
    
    return render_template(
        'dashboard/index.html',
        total_usuarios=total_usuarios,
        total_obras=total_obras,
        total_comunidades=total_comunidades,
        total_avaliacoes=total_avaliacoes,
        ultimos_itens=ultimos_itens,
        meses_dados=meses_dados,
        valores_dados=valores_dados,
        tipos_labels=tipos_labels,
        tipos_valores=tipos_valores
    )

