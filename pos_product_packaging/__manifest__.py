# -*- coding: utf-8 -*-
{
    'name': 'POS Product Packaging',
    'version': '19.0.1.1.0',
    'category': 'Point of Sale',
    'summary': 'Allow adding products by packaging quantity in POS',
    'description': """
        This module allows POS users to add products using packaging.

        In Odoo 19 packagings are units of measure. A packaging is a uom.uom
        record listed under "Packagings" on the product (product.template.uom_ids),
        and this module lets the POS sell in those units.

        Features:
        - Select a packaging (e.g. Box, Carton, Pallet) when adding a product
        - Enter a package count instead of a unit quantity
        - Automatically calculates total units and price
        - Shows the package count and packaging name on the order line
        - Keeps two packagings of the same product on separate lines, and adds
          up the package count when the same packaging is chosen again

        Tick which units the POS may offer under
        Point of Sale > Configuration > POS Packagings.

        Credits
        -------
        Brice Tchams reported the Odoo 19 incompatibility, identified that
        packagings live on uom.uom rather than product.uom, and contributed the
        multi-packaging cart design that keeps two packaging sizes of the same
        product on separate order lines.
    """,
    'author': 'Mohamed Yaseen Dahab, Brice Tchams',
    'maintainer': 'Mohamed Yaseen Dahab',
    'depends': ['point_of_sale', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_order_views.xml',
        'views/uom_uom_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_product_packaging/static/src/js/packaging_popup.js',
            'pos_product_packaging/static/src/js/pos_store.js',
            'pos_product_packaging/static/src/js/orderline.js',
            'pos_product_packaging/static/src/js/pos_order_line.js',
            'pos_product_packaging/static/src/xml/packaging_popup.xml',
            'pos_product_packaging/static/src/xml/orderline.xml',
            'pos_product_packaging/static/src/xml/product_card.xml',
            'pos_product_packaging/static/src/css/packaging.css',
        ],
    },
    'images': ['static/description/screenshot_overview.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
