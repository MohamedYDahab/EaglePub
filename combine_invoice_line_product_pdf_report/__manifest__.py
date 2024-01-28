# -*- coding: utf-8 -*-
{
    'name': "gather same product in one invoice line pdf report",

    'summary': """
        At Creating Multiple Purchase Orders Bills, Purchase Order Lines with the Same Product Will be Combined in One Order Line""",

    'description': """
        At Creating Multiple Purchase Orders Bills, Purchase Order Lines with the Same Product Will be Combined in One Order Line
    """,
    'author': "Mohamed Yaseen Dahab",
    'website': "https://www.odoo.com",

    'category': 'Purchase',
    'version': '0.1',
    'depends': ['base', 'purchase','account'],
    'data': [
        'security/ir.model.access.csv',
        'views/inherit_account_report.xml',
        'views/account_move.xml',
    ],
    'license': 'LGPL-3',

}
