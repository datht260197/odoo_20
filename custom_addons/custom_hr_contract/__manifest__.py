# Part of custom_hr_contract. See LICENSE file for full copyright and licensing details.
{
    'name': 'Vietnamese HR Contract Extension',
    'version': '20.0.1.0.0',
    'summary': 'Vietnamese labor contract fields, allowances, and official A4 PDF report',
    'description': """
        Extends HR module with Vietnamese localization fields:
        - Citizen ID (CCCD) details on employee
        - Permanent and temporary address fields
        - Tax ID and social insurance number
        - Contract categories and itemized allowances on employee records
        - Pure Python Vietnamese currency number-to-words converter
        - Official Vietnamese Labor Contract A4 QWeb PDF report
        - Conditional draft watermark for unsigned contracts
    """,
    'category': 'Human Resources',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/custom_hr_contract_security.xml',
        'security/ir.access.csv',
        'views/hr_employee_views.xml',
        'views/hr_version_views.xml',
        'report/hr_contract_report_views.xml',
        'report/hr_contract_template.xml',
    ],
    'assets': {},
    'installable': True,
    'application': False,
}
