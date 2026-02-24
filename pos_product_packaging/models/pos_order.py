# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    packaging_id = fields.Many2one(
        'product.packaging',
        string='Packaging',
        help='Product packaging used for this line'
    )
    package_qty = fields.Float(
        string='Package Qty',
        digits='Product Unit of Measure',
        default=0,
        help='Number of packages ordered'
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Define fields to load in POS for order lines"""
        fields = super()._load_pos_data_fields(config_id)
        fields.extend(['packaging_id', 'package_qty'])
        return fields


class PosOrder(models.Model):
    _inherit = 'pos.order'