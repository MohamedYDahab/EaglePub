# -*- coding: utf-8 -*-
{
    'name': 'Lot & Expiry Date in Invoice',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Display Lot/Serial Numbers and Expiry Dates on Invoice Lines and PDF Reports',
    'description': """
Lot & Expiry Date in Invoice
============================
This module adds lot/serial numbers and expiry dates information to invoice lines.

Features:
---------
* Displays lot/serial numbers linked to invoice lines from related stock moves
* Shows expiry dates for tracked products
* Adds lot and expiry information to invoice PDF reports
* Works with both customer invoices (from sales) and vendor bills (from purchases)
* Supports products with lot tracking and expiration date tracking

Technical Details:
-----------------
* Computes lots from sale order lines or purchase order lines stock moves
* Handles cases where products may not have expiration dates
* Properly formats expiry dates for display
    """,
    'author': 'Mohammed Yaseen Dahab',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'stock',
        'sale_stock',
        'purchase_stock',
        'product_expiry',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'report/invoice_report_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
