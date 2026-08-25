{
    'name': 'Demand Forecasting',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Forecast demand per product and warehouse, and check your reordering rules against it',
    'description': """
Demand Forecasting
==================
Odoo's forecasted quantity adds up the documents you already have: confirmed
sales orders out, purchase orders in. It is an accurate projection of paperwork,
and it says nothing about the orders that have not arrived yet.

This forecasts the demand itself, from your own sales history, and it shows the
months it worked from so the number can be argued with rather than taken on
faith.

How it forecasts
----------------
From your own confirmed sales history, bucketed by month, using one of three
methods you choose per run:

* **Average** - the mean of recent months. Blunt, stable, hard to argue with.
* **Weighted average** - recent months count for more.
* **Exponential smoothing** - the standard approach, with the smoothing factor
  in your hands rather than hidden.

Any of them can apply a **seasonal index** worked out from the same month in
previous years, when there is enough history to justify one.

It shows its working
--------------------
Every forecast line carries the months of history behind it, the demand in each
of them, and the seasonal factor applied. A forecast you cannot explain to the
person who has to sign the purchase order is worth nothing.

Thin history is labelled as thin rather than dressed up. A product with two
months of sales gets a number and a warning, not false confidence.

It checks your reordering rules
-------------------------------
Where a product already has a reordering rule, the forecast is compared against
it and any disagreement is reported - a minimum that will run you out, or one
holding stock you do not need.

Nothing is changed automatically. Reordering rules are yours to set.
    """,
    'author': 'Mohamed Yaseen Dahab',
    'website': 'https://www.speedy-world.com',
    'license': 'OPL-1',
    'price': 199.00,
    'currency': 'USD',
    'depends': ['stock', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/demand_forecast_views.xml',
        'wizard/demand_forecast_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
