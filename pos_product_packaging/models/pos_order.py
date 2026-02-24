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

    @api.model
    def _order_fields(self, ui_order):
        """Extend to include packaging fields from UI order"""
        order_fields = super()._order_fields(ui_order)
        return order_fields

    def _prepare_order_line(self, order_line):
        """Prepare order line values including packaging info"""
        vals = super()._prepare_order_line(order_line)
        vals.update({
            'packaging_id': order_line[2].get('packaging_id', False),
            'package_qty': order_line[2].get('package_qty', 0),
        })
        return vals

    @api.model
    def _process_order(self, order, draft, existing_order):
        """Process order with packaging information"""
        return super()._process_order(order, draft, existing_order)
