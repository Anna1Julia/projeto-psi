#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para dividir style-modern.css em módulos preservando 100% do conteúdo
"""

import re
from pathlib import Path

def split_css():
    css_file = Path('app/static/css/style-modern.css')
    content = css_file.read_text(encoding='utf-8')
    
    modules = {
        'variables.css': [],
        'base.css': [],
        'navbar.css': [],
        'cards.css': [],
        'buttons.css': [],
        'forms.css': [],
        'modals.css': [],
        'homepage.css': [],
        'dashboard.css': [],
        'components.css': [],
        'utilities.css': []
    }
    
    # Dividir em blocos por comentários principais
    lines = content.split('\n')
    current_module = 'components.css'
    buffer = []
    
    for line in lines:
        # Detectar seção por comentários
        if '/* THEME DARK */' in line or ':root' in line and not buffer:
            current_module = 'variables.css'
        elif '/* GLOBAL */' in line or 'html, body' in line:
            current_module = 'base.css'
        elif '/* Navbar' in line or '.app-navbar' in line or '.navbar' in line:
            current_module = 'navbar.css'
        elif '/* Cards' in line or '.card {' in line:
            current_module = 'cards.css'
        elif '/* Buttons' in line or '.btn' in line and '{' in line:
            current_module = 'buttons.css'
        elif '/* Forms' in line or '.form-' in line:
            current_module = 'forms.css'
        elif '/* Modal' in line or '.modal' in line:
            current_module = 'modals.css'
        elif '/* Homepage' in line or '.hero-' in line:
            current_module = 'homepage.css'
        elif '/* Dashboard' in line or '.dashboard' in line:
            current_module = 'dashboard.css'
        elif '/* Utility' in line or '/* Utilities' in line:
            current_module = 'utilities.css'
        
        modules[current_module].append(line)
    
    # Salvar módulos
    modules_dir = Path('app/static/css/modules')
    modules_dir.mkdir(exist_ok=True)
    
    for name, lines in modules.items():
        if lines:
            module_file = modules_dir / name
            module_file.write_text('\n'.join(lines), encoding='utf-8')
            print(f'✓ {name}: {len(lines)} linhas')
    
    # Criar arquivo principal de imports
    main_css = """/* MemóriaViva - Modular CSS */
@import url('modules/variables.css');
@import url('modules/base.css');
@import url('modules/navbar.css');
@import url('modules/cards.css');
@import url('modules/buttons.css');
@import url('modules/forms.css');
@import url('modules/modals.css');
@import url('modules/components.css');
@import url('modules/homepage.css');
@import url('modules/dashboard.css');
@import url('modules/utilities.css');
"""
    
    Path('app/static/css/main.css').write_text(main_css, encoding='utf-8')
    print('✓ main.css criado')

if __name__ == '__main__':
    split_css()
