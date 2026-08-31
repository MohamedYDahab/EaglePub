# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductUom(models.Model):
    _inherit = 'uom.uom'

    available_in_pos = fields.Boolean(
        string='Available in POS',
        default=False,
        help='If checked, this packaging will show in POS packaging selection popup'
    )

    @api.model
    def _load_pos_data_fields(self, config):
        data = super()._load_pos_data_fields(config)
        if 'available_in_pos' not in data:
            data.append('available_in_pos')
        return data
