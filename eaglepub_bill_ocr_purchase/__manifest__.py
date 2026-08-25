{
    'name': 'Vendor Bill OCR - Purchase Orders',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Match a digitised bill to its purchase order and flag the difference',
    'description': """
Vendor Bill OCR - Purchase Orders
=================================
A bridge, not an app. Install Vendor Bill OCR and Purchase together and this
appears on its own.

What it adds
------------
When a purchase order reference is printed on the supplier's invoice, the
digitised bill is linked to that order.

More usefully, the bill total is compared against the order total, and a
difference is **flagged on the bill** rather than left to be noticed at
payment time. Catching that a supplier billed more than they quoted is the
whole reason to hold a purchase order in the first place.

The link is recorded and the difference reported. Nothing is corrected
automatically, because which of the two figures is wrong is a judgement only
a person can make.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'LGPL-3',
    'depends': ['eaglepub_bill_ocr', 'purchase'],
    'data': [
        'views/account_move_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': True,
}
