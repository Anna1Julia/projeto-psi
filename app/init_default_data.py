"""
Módulo para criar dados padrão: conta MemóriaViva e comunidade oficial
"""
from .models import db, Usuario, Community

def create_default_account_and_community():
    """
    Cria a conta oficial MemóriaViva e a comunidade padrão
    """
    try:
        # Verificar primeiro o novo email oficial
        memoria_viva_user = Usuario.query.filter_by(email='memoriavivaoficial@gmail.com').first()
        
        # Se não existir, verificar o email antigo
        if not memoria_viva_user:
            memoria_viva_user = Usuario.query.filter_by(email='memoriaviva@oficial').first()
            
            # Se o usuário antigo existir, atualizar para o novo email
            if memoria_viva_user:
                print("📝 Migrando conta MemóriaViva para novo email...")
                memoria_viva_user.email = 'memoriavivaoficial@gmail.com'
                memoria_viva_user.is_admin = True
                memoria_viva_user.role = 'admin'
                db.session.commit()
                print("✅ Conta MemóriaViva migrada com sucesso!")
            else:
                # Criar nova conta com o novo email
                print("📝 Criando conta oficial MemóriaViva...")
                memoria_viva_user = Usuario(
                    nome='MemóriaViva',
                    email='memoriavivaoficial@gmail.com',
                    is_admin=True,  # Conta oficial é administradora
                    role='admin'
                )
                memoria_viva_user.senha = 'memoriaviva123'  # Usa o setter que gera hash
                db.session.add(memoria_viva_user)
                db.session.commit()
                print("✅ Conta MemóriaViva criada com sucesso!")
        else:
            # Usuário já existe, garantir que tenha permissões de admin
            if not memoria_viva_user.is_admin or memoria_viva_user.role != 'admin':
                print("📝 Atualizando permissões da conta MemóriaViva...")
                memoria_viva_user.is_admin = True
                memoria_viva_user.role = 'admin'
                db.session.commit()
                print("✅ Permissões atualizadas com sucesso!")
            else:
                print("✓ Conta MemóriaViva já existe com permissões corretas")
        
        # Verificar se a comunidade MemóriaViva já existe
        memoria_viva_community = Community.query.filter_by(name='MemóriaViva').first()
        
        if not memoria_viva_community:
            print("📝 Criando comunidade oficial MemóriaViva...")
            memoria_viva_community = Community(
                owner_id=memoria_viva_user.id,
                name='MemóriaViva',
                description='Comunidade oficial do MemóriaViva. Participe das discussões sobre acervos, tradições e cultura popular!',
                status='active',
                is_filtered=False
            )
            db.session.add(memoria_viva_community)
            db.session.commit()
            print("✅ Comunidade MemóriaViva criada com sucesso!")
        else:
            print("✓ Comunidade MemóriaViva já existe")
            
    except Exception as e:
        print(f"❌ Erro ao criar dados padrão: {e}")
        db.session.rollback()
        raise
