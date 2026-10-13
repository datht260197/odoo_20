# -*- coding: utf-8 -*-
{
    'name': 'Enterprise Approval Management',
    'version': '20.0.1.0.0',
    'category': 'Human Resources/Approvals',
    'summary': 'Enterprise Approval Management System - Multi-stage workflows, RBAC and audit trail',
    'description': """
Enterprise Approval Management System
=====================================
Digitalizes company request and approval workflows:
- Categories: Payments, Leaves, Procurements, Vehicle & Meeting Rooms, Contracts
- Multi-stage approval workflow with direct manager and assigned approvers
- Strict role-based security: User / Approver / Manager
- Modern UI with Chatter, audit trail and document tracking
    """,
    'author': 'Enterprise Solution',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'hr',
    ],
    'data': [
        # 1. Security groups & ir.access (must load first)
        'security/approval_security.xml',
        'security/ir.access.csv',

        # 2. System data
        'data/ir_sequence_data.xml',
        'data/approval_category_data.xml',

        # 3. Wizards
        'views/approval_reject_wizard_views.xml',

        # 4. User interface
        'views/approval_stage_views.xml',
        'views/approval_category_views.xml',
        'views/approval_request_views.xml',
        'views/approval_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
