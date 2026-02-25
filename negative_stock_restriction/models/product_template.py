from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    allow_negative_stock = fields.Boolean(
        string="Allow Negative Stock",
        help="If checked, this product is exempt from negative stock restrictions. "
             "Sales and transfers can proceed even when stock goes below zero.",
        default=False,
    )
