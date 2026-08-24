{
    'name': 'Purchase Target',
    'version': '19.0.1.7.0',
    'category': 'Inventory/Purchase',
    'summary': 'Set and track purchase targets per vendor and product, '
               'measured on goods actually received',
    'description': """
Purchase Targets
================
Allows Purchase Managers to set targets per vendor on specific products,
measured on what was physically received rather than what was ordered.

Features:

- Define purchase targets per vendor and product
- Target by received amount or received quantity
- Achievement read from done stock moves linked to confirmed purchase orders,
  attributed to the period the goods actually arrived in
- Returns to vendor are netted off
- Auto-compute period dates (monthly, quarterly, yearly, custom)
- Auto-renew to the next period
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'depends': ['purchase', 'purchase_stock', 'stock', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/purchase_target_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/purchase_target_report_wizard_views.xml',
        'report/purchase_target_report.xml',
        'report/purchase_target_report_templates.xml',
    ],
    # Loaded only when the database has demonstration data enabled.
    'demo': [
        'demo/purchase_target_demo.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'price': 39.00,
    'currency': 'EUR',
    'license': 'OPL-1',
}
