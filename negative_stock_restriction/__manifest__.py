{
    'name': 'Negative Stock Restriction',
    'version': '18.0.1.0.0',
    'summary': 'Prevent negative inventory in Stock and POS',
    'category': 'Inventory/Inventory',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['stock', 'point_of_sale'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'negative_stock_restriction/static/src/js/stock_check.js',
            'negative_stock_restriction/static/src/xml/stock_check.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
}
