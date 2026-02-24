# -*- coding: utf-8 -*-
{
    'name': 'Lots & Serials in Invoice Lines',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Display Lot/Serial Numbers and Expiry Dates on SO, PO, Invoice Lines and PDF Reports',
    'description': """
Lots & Serials in Invoice Lines
===============================
Track lot/serial numbers and expiry dates across the full sales cycle —
from Sale Orders and Purchase Orders through to Invoices and PDF reports.

Features
--------
* Lot/serial numbers visible on Sale Order, Purchase Order, and Invoice lines
* Expiry dates displayed alongside lots
* Manual lot selection for direct invoices (not linked to SO/PO)
* Lot & expiry info printed on Invoice PDF reports
* Popup to browse lot details with expiry dates
* Cross-channel: works with customer invoices (from sales) and vendor bills (from purchases)
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'sale_stock',
        'purchase_stock',
        'product_expiry',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_lot_tree.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/account_move_views.xml',
        'report/invoice_report_templates.xml',
    ],
    'images': ['static/description/screenshot_overview.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
