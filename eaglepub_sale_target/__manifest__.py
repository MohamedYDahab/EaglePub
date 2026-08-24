{
    'name': 'Sales Target',
    'version': '19.0.1.7.0',
    'category': 'Sales',
    'summary': 'Set and track revenue targets for salespeople on specific products',
    'description': """
Sales Targets
=============
Allows Sales Managers to set revenue targets for individual salespeople or sales teams
on specific products with configurable time periods.

Features:
- Define revenue targets per salesperson and product
- Auto-compute period dates (monthly, quarterly, yearly, custom)
- Track achieved amount from confirmed Sale Orders
- Visual progress bar showing target completion
- Computed "Qty to Reach Target" indicator
- Salespeople can only view their own targets
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'depends': ['sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'security/sale_target_security.xml',
        'views/sale_target_views.xml',
        'wizard/sale_target_report_wizard_views.xml',
        'report/sale_target_report.xml',
        'report/sale_target_report_templates.xml',
    ],
    # Loaded only when the database has demonstration data enabled.
    'demo': [
        'demo/sale_target_demo.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'currency': 'EUR',
    'support': 'mohamed.yaseen.dahab@gmail.com',
    'phone': '+971559354935',
    'price': 49.00,
    'license': 'OPL-1',
}




