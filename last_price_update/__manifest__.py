# -*- coding: utf-8 -*-
{
    'name': 'Last Customer Price Update',
    'version': '17.0.1.0.0',
    'summary': 'Update SO/POS prices to last price for same customer',
    'description': """
        Adds a "Last Price" button to:
        - Sale Orders: updates line prices to last confirmed SO/POS price
          for the same customer + product
        - POS: updates order line prices from last SO/POS order
          for the selected customer + product
        Falls back to Odoo default price if no previous order found.
    """,
    'category': 'Sales/Sales',
    'author': 'Mohamed Yaseen Dahab',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'point_of_sale'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'last_price_update/static/src/js/last_price_button.js',
            'last_price_update/static/src/xml/last_price_button.xml',
        ],
    },
    'images': ['static/description/screenshot_overview.gif'],

    'installable': True,
    'auto_install': False,
}
