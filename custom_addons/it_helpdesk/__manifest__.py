# -*- coding: utf-8 -*-
{
    'name': 'IT Helpdesk & Task Management',
    'summary': 'IT support tickets, IT assets, and department role templates',
    'description': """
IT Helpdesk & Task Management
=============================
- IT support ticket tracking with auto-generated sequences and SLAs
- Reusable job templates for routine IT tasks
- IT Asset inventory and tracking (laptops, desktops, printers, network)
- Security with IT User / IT Manager roles and record-level rules
- Telegram notifications
    """,
    'author': 'IT Department',
    'website': 'https://www.yourcompany.com',
    'category': 'Services/Helpdesk',
    'version': '20.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base', 'hr', 'mail', 'project', 'portal'],
    'data': [
        # 1. Security groups & ir.access (must load first)
        'security/it_security.xml',
        'security/ir.access.csv',

        # 2. Data
        'data/it_config_data.xml',
        'data/it_role_template_data.xml',
        'data/it_team_data.xml',

        # 3. Views
        'views/it_ticket_views.xml',
        'views/it_asset_views.xml',
        'views/it_portal_templates.xml',
        'views/it_department_role_template_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
