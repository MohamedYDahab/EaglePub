# -*- coding: utf-8 -*-
{
    'name': 'POS Product Packaging',
    'version': '17.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Allow adding products by packaging quantity in POS',
    'description': """
        This module allows POS users to add products using packaging.
        
        Features:
        - Select product packaging (e.g., Box, Carton, Pallet)
        - Enter package quantity instead of unit quantity
        - Automatically calculates total units and price
        - Displays package quantity on order line
    """,
    'author': 'Mohamed Yaseen Dahab',
    'depends': ['point_of_sale', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_order_views.xml',
        'views/product_packaging_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_product_packaging/static/src/js/models.js',
            'pos_product_packaging/static/src/js/packaging_popup.js',
            'pos_product_packaging/static/src/js/pos_store.js',
            'pos_product_packaging/static/src/xml/packaging_popup.xml',
            'pos_product_packaging/static/src/xml/orderline.xml',
            'pos_product_packaging/static/src/css/packaging.css',
        ],
    },
    'images': ['static/description/screenshot_overview.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
