{
    'name': 'Project Security Tier',
    'version': '1.0.0',
    'category': 'Services/Project',
    'summary': 'Multi-level Role-Based Access Control, Stage Transition Locks, and Allocated Hours Protection',
    'author': 'Antigravity',
    'license': 'LGPL-3',
    'depends': ['base', 'project'],
    'data': [
        'security/project_security_tier_groups.xml',
        'security/ir.access.csv',
        'views/project_task_type_views.xml',
        'views/project_task_views.xml',
    ],
    'application': False,
    'installable': True,
}
