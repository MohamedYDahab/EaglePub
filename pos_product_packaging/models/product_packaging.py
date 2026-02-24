# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    available_in_pos = fields.Boolean(
        string='Available in POS',
        default=True,
        help='If checked, this packaging will be available in Point of Sale'
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        data = super()._load_pos_data_fields(config_id)
        if 'available_in_pos' not in data:
            data.append('available_in_pos')
        return data

    @api.model
    def _load_pos_data_domain(self, data):
        # Override to load all packagings with available_in_pos=True
        # instead of only those with barcodes
        return [('available_in_pos', '=', True)]
