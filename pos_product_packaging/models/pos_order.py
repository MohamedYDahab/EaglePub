# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    packaging_id = fields.Many2one(
        'uom.uom',
        string='Packaging',
        help='Packaging used for this line'
    )
    package_qty = fields.Float(
        string='Package Qty',
        digits='Product Unit of Measure',
        default=0,
        help='Number of packages ordered'
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        fields_list.extend(['packaging_id', 'package_qty'])
        return fields_list


class PosOrder(models.Model):
    _inherit = 'pos.order'
