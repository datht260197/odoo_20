# -*- coding: utf-8 -*-
{
    'name': 'Enterprise Approval Management',
    'version': '20.0.1.1.0',
    'category': 'Human Resources/Approvals',
    'summary': 'Enterprise Approval Management System - 2FA OTP Digital Signatures, A4 Approval Slip Reports, Multi-stage workflows, RBAC and audit trail',
    'description': """
Enterprise Approval Management System
=====================================
Digitalizes company request and approval workflows:
- Categories: Payments, Leaves, Procurements, Vehicle & Meeting Rooms, Contracts
- Two-Factor OTP Digital Signature Verification on approval actions
- Configurable A4 Approval Slip QWeb PDF Printout with draft watermark and audit seals
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

        # 2. System data & mail templates
        'data/ir_sequence_data.xml',
        'data/approval_category_data.xml',
        'data/mail_template_data.xml',

        # 3. Wizards
        'views/approval_reject_wizard_views.xml',
        'views/approval_signature_otp_wizard_views.xml',
        'views/approval_slip_print_wizard_views.xml',

        # 4. User interface
        'views/approval_stage_views.xml',
        'views/approval_category_views.xml',
        'views/approval_request_views.xml',
        'views/approval_menus.xml',

        # 5. Reports (paperformat, report actions and QWeb templates)
        'report/approval_report_views.xml',
        'report/approval_slip_template.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
