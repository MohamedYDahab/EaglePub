{
    'name': 'POS Reports Pack',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Shift close, cashier performance, product mix, hourly sales and payment breakdown - PDF and Excel, Arabic ready',
    'description': """
POS Reports Pack
================
Odoo tells you what a point of sale sold. It is far less forthcoming about
which cashier sold it, at what hour, through which payment method, and how a
shift actually closed. This fills that in.

Five reports, one screen
------------------------
* **Shift / Z-report** - every session in the period: opened, closed, orders,
  sales, tax and average ticket.
* **Cashier performance** - orders, sales, discount given and share of the
  total, per cashier.
* **Product mix** - what actually moved, by quantity and by value.
* **Hourly sales** - where the day's takings really come from, in your own
  timezone rather than UTC.
* **Payment breakdown** - cash against card against everything else.

Every one exports to PDF and to Excel.

Arabic and RTL
--------------
Headings, column labels and alignment all flip for Arabic users. The Excel
sheets right-align text and left-align figures, the way an Arabic reader
expects - not an English sheet with translated words dropped into it.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'OPL-1',
    'price': 49.00,
    'currency': 'EUR',
    'depends': ['eaglepub_pos_base'],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [
        'security/ir.model.access.csv',
        'wizard/pos_report_wizard_views.xml',
        'report/pos_report.xml',
        'report/pos_report_templates.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
