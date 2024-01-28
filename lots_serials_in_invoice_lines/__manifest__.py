# -*- coding: utf-8 -*-
{
    'name': "lots and Serials in invoice lines",
    'summary': "Show Lots and Serials in Invoice Lines, and Invoice PDF Report",
    'description': """
        Module Allow Tracking Products From Orders to Delivery to invoice - Show Lots and Serials in Invoice Lines, and Invoice PDF Report
    """,
    'author': "Mohamed Yaseen Dahab",
    'website': "https://www.speedy-world.com",
    'category': 'Accounting',
    'version': '0.1',
    'depends': ['account','sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order.xml',
        'views/purchase_order.xml',
        'views/stock_lot_tree.xml',
        'views/account_move.xml',
        'views/account_report.xml',
    ],
    'license': 'LGPL-3',

}
