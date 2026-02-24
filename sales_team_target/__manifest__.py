# -*- coding: utf-8 -*-
{
    'name': 'Sales Team Target',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Monthly sales targets per salesperson with POS & Invoice tracking',
    'description': """
        Sales Team Target Management
        ============================
        - Define monthly sales targets per salesperson
        - Track achievement from posted invoices and POS orders
        - Salespersons see only their own targets
        - Managers see full team performance
        - Bulk target creation for entire team
        - Copy last month targets to new month
        - Dashboard with comparison charts
        - PDF & Excel performance reports with Arabic/RTL support
    """,
    'author': 'Mohamed Yaseen Dahab',
    'license': 'OPL-1',
    'price': 29.99,
    'currency': 'USD',
    'depends': [
        'sale',
        'point_of_sale',
        'account',
        'sales_team',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/sales_target_views.xml',
        'views/dashboard_action.xml',
        'wizard/bulk_target_wizard_views.xml',
        'wizard/copy_target_wizard_views.xml',
        'wizard/sales_target_report_wizard_views.xml',
        'report/sales_target_report.xml',
        'report/sales_target_report_templates.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sales_team_target/static/src/css/dashboard.css',
            'sales_team_target/static/src/js/dashboard.js',
            'sales_team_target/static/src/xml/dashboard.xml',
        ],
    },

    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
