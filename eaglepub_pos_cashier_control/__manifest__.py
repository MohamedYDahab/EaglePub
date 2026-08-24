{
    'name': 'POS Cashier Control',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Discount ceilings, line-delete locks and manager approval per cashier',
    'description': """
POS Cashier Control
===================
Odoo lets any cashier discount an order to nothing and delete lines at will.
This app puts a policy behind the till.

Policies
--------
Build a policy once and assign it to as many cashiers as you like:

* **Maximum discount** a cashier may apply to a line.
* **Allow line deletion** - off means lines can only be added, not removed.
* **Allow price change** - off means the pricelist decides, not the cashier.
* **Maximum order total** before a manager has to approve.

Manager override
----------------
A supervisor unlocks a single order from the till with the manager PIN, or is
waved through automatically if they hold the POS Manager Override group. The
PIN is checked on the server, so it is never readable from the browser.

Enforced twice
--------------
Limits are applied in the till *and* re-checked when the order reaches the
server, so an order cannot be edited past its policy on the way through.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'OPL-1',
    'price': 59.00,
    'currency': 'EUR',
    'depends': ['eaglepub_pos_base'],
    'data': [
        'security/ir.model.access.csv',
        'views/eaglepub_pos_policy_views.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'eaglepub_pos_cashier_control/static/src/js/cashier_control.js',
            'eaglepub_pos_cashier_control/static/src/js/order_limits.js',
            'eaglepub_pos_cashier_control/static/src/js/override_button.js',
            'eaglepub_pos_cashier_control/static/src/xml/override_button.xml',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
