# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Ready-Mix Concrete: Fast ERP Master Data Migration',
    'version': '20.0.1.0.0',
    'category': 'Technical/Migration',
    'summary': 'Idempotent Master Data Migration Wizard from Legacy Fast ERP',
    'description': """
Ready-Mix Concrete (RMC) Fast ERP Migration Wizard
==================================================
- Transient wizard supporting idempotent bulk Upsert migrations from Fast ERP
- Migrates Customers & Material Suppliers (res.partner)
- Migrates Concrete Grades & Raw Ingredients (product.template)
- Migrates Construction Sites & Historical Quota Balances (project.project)
- Fully idempotent using Odoo ORM create/write with detailed execution logging
    """,
    'author': 'DatHT',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'contacts',
        'rmc_inventory_plant',
        'rmc_project_site',
    ],
    'data': [
        'security/ir.access.csv',
        'views/res_partner_views.xml',
        'views/rmc_fast_migration_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
