# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Employee Contracts & DOCX Generator',
    'version': '20.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Employee contracts management with dynamic DOCX template generation and Vietnamese localization support',
    'description': """
        Modernized Employee Contracts for Odoo 20:
        - Manage employee contracts, types, wage and working schedules
        - Upload and manage custom DOCX contract templates (.docx with Jinja2 placeholders)
        - Dynamic DOCX contract generation populated with employee, job, salary and Vietnamese localized data
        - Official Vietnamese number-to-words currency integration
        - Strict print isolation protecting QWeb PDF reports
    """,
    'author': 'Custom',
    'license': 'LGPL-3',
    'website': 'https://www.odoo.com/page/employees',
    'depends': [
        'base',
        'hr',
        'mail',
        'custom_hr_contract',
    ],
    'external_dependencies': {
        'python': ['docxtpl'],
    },
    'data': [
        'security/ir.access.csv',
        'data/hr_contract_data.xml',
        'views/hr_contract_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
