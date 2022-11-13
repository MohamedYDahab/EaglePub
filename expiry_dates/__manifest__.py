# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Expiry Date on Invoice Line',
    'sequence': 1,
    'author' : 'Mohamed Yaseen Dahab',
    'category': 'Accounting/Accounting',
    'summary': 'Add Expiry Date in an Invoice Line and Inventory Adjustment Line',
    'description': """
            ### Add Expiration Date on Invoice Line / Inventory Adjustment
            
            1] add lot/serial and Expiration Date in Sale Order Line and Invoice Line
            2] add Expiration Date in Invoice PDF Report
            3] add Expiration Date on Inventory Adjustment Line
            4] Adjust Lot Expiration Date from Inventory Adjustment Lines
    
    
    """,
    'version': '1.0',
    'depends': ['base','stock','product_expiry','sale','account'],
    'data': [
        'views/inherit_invoice.xml',
        'views/inherit_stock.xml',
        'report/inherit_invoice_report.xml'
    ],
    'images': ['images/main_screenshot.png''images/expiry_adjust.PNG','images/invoice_report.PNG'],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
