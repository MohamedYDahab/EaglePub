{
    'name': 'Stock Restrict Negative Quantity in PoS SO and Stock Move',
    'version': '19.0.2.0.0',
    'summary': 'Prevent negative inventory in Stock, POS, and Sales',
    'description': """
        Comprehensive negative stock restriction module:
        - Hard block or soft warning modes
        - Works in Stock Transfers, POS, and Sale Orders
        - Per-product, per-category, per-warehouse exceptions
        - Real-time stock display in POS with color-coded badges
        - Auto-hide out-of-stock products in POS
        - Configurable low-stock threshold warnings
        - Manager override with PIN for hard-blocked orders
        - Bypass security group for authorized users
    """,
    'category': 'Inventory/Inventory',
    'author': 'Mohamed Yaseen Dahab',
    'license': 'OPL-1',
    'price': 49.90,
    'currency': 'USD',
    'depends': ['stock', 'point_of_sale', 'sale_management'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/res_config_settings_views.xml',
        'views/product_template_views.xml',
        'views/product_category_views.xml',
        'views/stock_warehouse_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'negative_stock_restriction/static/src/css/pos_stock.css',
            'negative_stock_restriction/static/src/js/manager_override_popup.js',
            'negative_stock_restriction/static/src/xml/manager_override_popup.xml',
            'negative_stock_restriction/static/src/js/stock_check_button.js',
            'negative_stock_restriction/static/src/xml/stock_check_button.xml',
            'negative_stock_restriction/static/src/js/stock_check_payment.js',
            'negative_stock_restriction/static/src/js/pos_stock_badges.js',
            'negative_stock_restriction/static/src/xml/pos_stock_badges.xml',
        ],
    },
    'images': ['static/description/negative_stock_prevention.png'],
    'installable': True,
    'auto_install': False,
}
