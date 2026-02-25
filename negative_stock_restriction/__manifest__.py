# -*- coding: utf-8 -*-
{
    'name': 'Negative Stock Restriction',
    'version': '17.0.1.0.0',
    'summary': 'Prevent negative inventory in Stock and POS',
    'description': """
        Prevents or warns when stock would go negative.
        Features:
        - Hard Block or Soft Warning mode (configurable)
        - Stock Transfer restriction (delivery orders)
        - Point of Sale restriction (real-time stock check)
        - User bypass group for Inventory Managers
        - Configurable via Settings > Inventory
    """,
    'category': 'Inventory/Inventory',
    'author': 'Mohamed Yaseen Dahab',
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
