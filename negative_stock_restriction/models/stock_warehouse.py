from odoo import models, fields


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    allow_negative_stock = fields.Boolean(
        string="Allow Negative Stock",
        help="If checked, this warehouse is exempt from negative stock "
             "restrictions. All transfers out of this warehouse will be allowed.",
        default=False,
    )
