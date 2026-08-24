{
    'name': 'POS Cashier Control - Employee Cashiers',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Apply cashier policies to badge-login employees, not just Odoo users',
    'description': """
POS Cashier Control - Employee Cashiers
=======================================
A bridge, not an app. Install POS Cashier Control and Employees in the Point
of Sale together and this appears on its own.

Why it exists
-------------
With badge login, the Odoo user behind a session is whoever opened the till -
often a supervisor who never touched the sale. The person who actually served
the customer is an **employee**, and without this bridge a policy attached to
an Odoo user simply never applies to them.

That failure is silent, which is the worst kind: the limits look configured
and quietly enforce nothing.

What it adds
------------
* A **POS Policy** field on the employee, under their HR settings.
* Policy resolution at the till and on the server now prefers the employee who
  rang the order up.
* An employee with no policy of their own falls back to the policy on their
  linked Odoo user, so you can set it in one place if that suits you.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'LGPL-3',
    'depends': ['eaglepub_pos_cashier_control', 'pos_hr'],
    'data': [
        'views/hr_employee_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'eaglepub_pos_cashier_control_hr/static/src/js/cashier_control_hr.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    # Appears by itself once both sides are present. A correctness fix nobody
    # remembers to install is not a fix.
    'auto_install': True,
}
