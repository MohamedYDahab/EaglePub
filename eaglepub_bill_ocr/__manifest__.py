{
    'name': 'Vendor Bill OCR & Digitisation',
    'version': '19.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Read vendor bills from PDF or photo into draft bills, with your own AI key',
    'description': """
Vendor Bill OCR & Digitisation
==============================
Drop in a PDF or a photograph of a supplier invoice and get a draft vendor
bill back - vendor, dates, reference, lines, taxes and totals - ready for a
human to check and post.

Bring your own key
------------------
Reading is done by a vision model you configure and pay for directly, so
there is no per-page fee to this app and no middleman holding your documents.
Nothing is sent anywhere until you enter a key.

It checks its own arithmetic
----------------------------
Extracted lines are re-added and compared against the totals printed on the
document. If they disagree the bill is flagged rather than quietly filled in
wrong, because a plausible number in the wrong field is worse than an obvious
blank.

Nothing posts itself
--------------------
Every result lands as a **draft** bill for review. The raw extraction is kept
on the record, so when a figure is queried you can see exactly what was read
off the page rather than guessing.

Vendors are matched on VAT number first, then on name. A vendor that cannot be
matched is left empty for you to pick rather than invented.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'OPL-1',
    'price': 199.00,
    'currency': 'USD',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'wizard/bill_ocr_upload_views.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
