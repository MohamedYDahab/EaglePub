{
    'name': 'EaglePub POS Base',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Shared foundation for the EaglePub Point of Sale suite',
    'description': """
EaglePub POS Base
=================
Groceries the rest of the EaglePub POS apps share, so they can be installed
side by side without each one shipping its own copy.

Provides
--------
* A manager PIN per point of sale, checked on the server so the value is
  never sent to the browser.
* A reusable PIN dialog for the till, and a ``askManagerPin()`` helper on the
  POS store that any EaglePub app can await.
* The "EaglePub / POS Manager" security group used to gate restricted actions.

Install this on its own and nothing changes; it exists to be depended on.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'LGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'security/eaglepub_pos_security.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'eaglepub_pos_base/static/src/js/pin_dialog.js',
            'eaglepub_pos_base/static/src/js/pos_store_ext.js',
            'eaglepub_pos_base/static/src/xml/pin_dialog.xml',
            'eaglepub_pos_base/static/src/css/eaglepub_pos.css',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
