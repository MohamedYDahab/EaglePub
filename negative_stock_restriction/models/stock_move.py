# -*- coding: utf-8 -*-
import logging
from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, **kwargs):
        """Override to check for negative stock before completing moves."""
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param(
            'negative_stock_restriction.enabled', 'True')
        stock_enabled = ICP.get_param(
            'negative_stock_restriction.stock_enabled', 'True')
        mode = ICP.get_param(
            'negative_stock_restriction.mode', 'hard')

        if enabled == 'True' and stock_enabled == 'True':
            bypass = self.env.user.has_group(
                'negative_stock_restriction.group_bypass_negative_stock')

            for move in self:
                if not move.product_id or move.product_id.type != 'product':
                    continue
                # Only check outgoing moves
                if not move.location_id.usage == 'internal':
                    continue
                if move.location_dest_id.usage == 'internal':
                    continue  # internal transfer, skip

                available = self.env['stock.quant']._get_available_quantity(
                    move.product_id,
                    move.location_id,
                    lot_id=move.lot_ids[:1] if move.lot_ids else None,
                    strict=False,
                )
                demand = move.quantity if hasattr(move, 'quantity') else move.product_uom_qty

                if available < demand:
                    product_name = move.product_id.display_name
                    location_name = move.location_id.complete_name
                    msg = _(
                        'Negative Stock Blocked!\n'
                        'Product: %(product)s\n'
                        'Available: %(available)s\n'
                        'Requested: %(demand)s\n'
                        'Location: %(location)s',
                        product=product_name,
                        available=available,
                        demand=demand,
                        location=location_name,
                    )
                    if mode == 'hard' and not bypass:
                        raise UserError(msg)
                    else:
                        _logger.warning(
                            'Negative stock warning: %s - '
                            'Available: %s, Demand: %s at %s (user: %s)',
                            product_name, available, demand,
                            location_name, self.env.user.name)

        return super()._action_done(**kwargs)
