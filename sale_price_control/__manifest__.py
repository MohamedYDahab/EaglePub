{
    'name': 'Sale Price Control With Password',
    'version': '17.0.7.0.0',
    'category': 'Sales',
    'summary': 'Prevent confirming sale orders with prices below cost without password authorization',
    'description': """
Sale Price Control
==================
- When user clicks Confirm on a sale order, checks all lines for below-cost pricing.
- If any line has price below cost, opens a password authorization wizard.
- Only users in "Allow Below Cost Price" group with a configured password can authorize.
- Password field added to user preferences.
- 100% server-side: no JavaScript, no browser cache issues.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'product'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'wizard/price_override_wizard_views.xml',
        'views/res_users_views.xml',
    ],
    'images': ['static/description/sale_price_control.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
