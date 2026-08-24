{
    'name': 'Sales Commission',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Commission plans per salesperson, on revenue or margin, from orders, invoices or payments',
    'description': """
Sales Commission
================
Work out what your salespeople have earned, from the documents you already
have, without a spreadsheet.

Plans, not formulas
-------------------
A plan says three things: **when** commission is earned, **what** it is
calculated on, and **at what rate**.

* Earned on a confirmed order, a posted invoice, or only once the customer
  has actually paid.
* Calculated on revenue or on **margin** - so discounting into a loss stops
  paying commission.
* Rates set per product, per product category, or one rate for everything.
  The first matching rule wins, so you can put the exceptions above the
  general case.

Assign a plan to as many salespeople as you like.

Auditable by construction
-------------------------
Every commission record keeps a line per source document line: the product,
the quantity, the base it was calculated on, the rate that applied and the
resulting amount. When someone queries a figure you can show them where it
came from rather than recomputing it.

Credit notes subtract. A refunded sale does not stay commissioned.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'OPL-1',
    'price': 69.00,
    'currency': 'USD',
    'depends': ['sale_management', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/commission_plan_views.xml',
        'views/commission_views.xml',
        'views/res_users_views.xml',
        'wizard/commission_compute_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
