{
    'name': 'Modern Cloud Theme',
    'summary': 'Clean, minimalist Slate & Blue backend theme inspired by modern cloud SaaS design',
    'description': """
        A lightweight, CSS-only backend theme that brings a clean, flat, modern
        cloud aesthetic to Odoo 20 Community. Features a pure white document
        canvas, floating pill search bar, subtle borders, and a refined
        Slate & Blue color palette.

        Key features:
        - Royal Blue primary brand color with Slate Gray accents
        - Ultra-clean white navbar with subtle bottom border
        - Floating pill-shaped search bar with rounded filter tags
        - Flat form sheets, clean kanban cards, polished list views
        - Strict print protection — zero theme bleed into QWeb PDF reports
        - Zero JavaScript — pure SCSS, maximum stability and performance
    """,
    'version': '20.0.1.0.0',
    'category': 'Themes/Backend',
    'license': 'LGPL-3',
    'author': 'Custom',
    'depends': ['base', 'web'],
    'assets': {
        'web._assets_primary_variables': [
            (
                'after',
                'web/static/src/scss/primary_variables.scss',
                'modern_cloud_theme/static/src/scss/primary_variables.scss',
            ),
        ],
        'web.assets_backend': [
            'modern_cloud_theme/static/src/scss/layout_navbar.scss',
            'modern_cloud_theme/static/src/scss/layout_control_panel.scss',
            'modern_cloud_theme/static/src/scss/layout_views.scss',
            'modern_cloud_theme/static/src/scss/print_protection.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
