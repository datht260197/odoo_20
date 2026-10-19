# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Ready-Mix Concrete: Inventory & Batching Plant',
    'version': '20.0.1.0.0',
    'category': 'Inventory/Ready-Mix Concrete',
    'summary': 'Multi-Plant Inventory, Silos, Aggregate Bins, and Static Density Matrix',
    'description': """
Ready-Mix Concrete (RMC) Inventory & Batching Plant Management
==============================================================
- Batching plant definition on warehouses with capacity and plant manager
- Specialized storage locations (silos, aggregate hoppers, admixture tanks)
- Product cross-system codes (BMES, ACS, Fast ERP) and concrete technical specs
- Active static aggregate density matrix per plant and raw material with moisture adjustments
- Automated volumetric and weight quantity conversions
    """,
    'author': 'DatHT',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'product',
        'stock',
        'uom',
        'hr',
    ],
    'data': [
        'security/ir.access.csv',
        'data/uom_and_category_data.xml',
        'views/stock_warehouse_views.xml',
        'views/stock_location_views.xml',
        'views/product_template_views.xml',
        'views/rmc_material_density_matrix_views.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
