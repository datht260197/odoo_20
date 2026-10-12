{
    'name': 'My Test Module',
    'version': '1.0.0',
    'summary': 'Module mẫu kiểm thử trên máy tính cá nhân',
    'description': """
        Module mẫu được tạo tự động để kiểm thử hiển thị giao diện Odoo 20 trên máy tính.
    """,
    'category': 'Customization',
    'author': 'Custom Developer',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.access.csv',
        'views/test_item_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
}
