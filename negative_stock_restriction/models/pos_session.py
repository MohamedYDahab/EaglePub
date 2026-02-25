# -*- coding: utf-8 -*-
from odoo import models, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def get_stock_for_products(self, product_ids, location_id=False):
        """RPC method called from POS frontend.
        Returns dict {product_id: qty_available} for the given product IDs.
        Uses the POS config warehouse/location if no location_id given."""
        result = {}
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param(
            'negative_stock_restriction.enabled', 'True')
        pos_enabled = ICP.get_param(
            'negative_stock_restriction.pos_enabled', 'True')
        mode = ICP.get_param(
            'negative_stock_restriction.mode', 'hard')

        if enabled != 'True' or pos_enabled != 'True':
            return {'enabled': False, 'mode': mode, 'stock': {}}

        # Determine location
        location = False
        if location_id:
            location = self.env['stock.location'].browse(location_id)
        else:
            # Try to get from current session config
            sessions = self.search(
                [('state', '=', 'opened'),
                 ('user_id', '=', self.env.uid)],
                limit=1)
            if sessions and sessions.config_id.picking_type_id:
                location = (
                    sessions.config_id.picking_type_id
                    .default_location_src_id)

        products = self.env['product.product'].browse(product_ids)
        for product in products:
            if product.type != 'product':
                result[product.id] = 9999999  # consumable/service
                continue
            if location:
                qty = self.env['stock.quant']._get_available_quantity(
                    product, location, strict=False)
            else:
                qty = product.qty_available
            result[product.id] = qty

        bypass = self.env.user.has_group(
            'negative_stock_restriction.group_bypass_negative_stock')

        return {
            'enabled': True,
            'mode': mode,
            'stock': result,
            'bypass': bypass,
        }
