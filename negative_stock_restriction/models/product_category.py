from odoo import models, fields


class ProductCategory(models.Model):
    _inherit = 'product.category'

    allow_negative_stock = fields.Boolean(
        string="Allow Negative Stock",
        help="If checked, all products in this category are exempt from "
             "negative stock restrictions.",
        default=False,
    )
