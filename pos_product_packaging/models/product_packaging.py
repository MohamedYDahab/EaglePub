# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    available_in_pos = fields.Boolean(
        string='Available in POS',
        default=True,
        help='If checked, this packaging will be available in Point of Sale'
    )


class PosDB(models.AbstractModel):
    """Ensure all packagings are loaded in POS"""
    _inherit = 'pos.session'

    @api.model
    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        if 'product.packaging' not in result:
            result.append('product.packaging')
        return result