# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Lot and Expiry Dates on Invoice Lines',
    'sequence': 1,
    'author': 'Mohamed Yaseen Dahab',
    'category': 'Accounting/Accounting',
    'summary': '',
    'description': """
        Adds Lots Name and Expiry Dates on Invoice Lines
        Adds Discount on PO Line
        Adds Is Bonus toggle in SO and PO

    """,
    'version': '1.0',
    'depends': ['base', 'stock', 'arabic_taxable_invoice_knk', 'account', 'sale', 'purchase', 'product_expiry'],
    'data': [
        'views/inherit_acc_move.xml',
        'views/inherit_stock.xml',
        'views/inherit_purchase_order_view.xml',
        'views/inherit_sale_order_view.xml',
        'report/inherit_invoice_report.xml',
    ],
    'images': ['images/main_screenshhot.png','images/main_screenshot.png','images/expiry_adjust.PNG', 'images/invoice_report.PNG', 'images/inventory_adjustment.PNG', 'images/invoice_line.PNG'],

    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
