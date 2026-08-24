{
    'name': 'Sales Commission - Point of Sale',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Commission till sales alongside orders and invoices',
    'description': """
Sales Commission - Point of Sale
================================
A bridge, not an app. Install Sales Commission and Point of Sale together and
this appears on its own.

What it adds
------------
Till sales count towards commission, using the same plans and the same rules
as everything else. A salesperson who sells over the counter in the morning
and on invoice in the afternoon is paid for both, on one commission record.

Basis is ignored for till sales, deliberately: an order is rung up, paid and
settled in one motion, so "confirmed", "invoiced" and "paid" are the same
instant and there is nothing to distinguish between.

POS refunds subtract, because a refund order carries negative quantities of
its own.

Switch it off per plan with **Include POS Sales** if a particular plan should
only cover invoiced business.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'LGPL-3',
    'depends': ['eaglepub_sale_commission', 'point_of_sale'],
    'data': [
        'views/commission_plan_views.xml',
        'views/commission_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    # Appears by itself once both sides are present, which is what makes it a
    # bridge rather than something else to remember to install.
    'auto_install': True,
}
