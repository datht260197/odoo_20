# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Ready-Mix Concrete: Construction Site & Project Hub',
    'version': '20.0.1.0.0',
    'category': 'Services/Ready-Mix Concrete',
    'summary': 'Concrete Construction Sites, Geofence GPS, Plant Routing, and Automated Analytic Accounts',
    'description': """
Ready-Mix Concrete (RMC) Construction Site Hub
==============================================
- Extends project.project to manage concrete construction sites
- GPS coordinate tracking with geofence discharge radius validation
- Primary and backup batching plant routing
- Automated analytic account generation for multi-dimensional cost tracking
- High-level progress and remaining contract quota metrics
- Standard concrete pouring construction stages
    """,
    'author': 'DatHT',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'project',
        'analytic',
        'rmc_inventory_plant',
    ],
    'data': [
        'data/project_stages_data.xml',
        'views/project_project_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
