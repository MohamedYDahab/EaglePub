import logging
from odoo import models, _
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, **kwargs):
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('negative_stock_restriction.enabled', 'True') == 'True' \
           and ICP.get_param('negative_stock_restriction.stock_enabled', 'True') == 'True':
            mode = ICP.get_param('negative_stock_restriction.mode', 'hard')
            bypass = self.env.user.has_group('negative_stock_restriction.group_bypass_negative_stock')
            for move in self:
                if not move.product_id or move.product_id.type != 'product':
                    continue
                if move.location_id.usage != 'internal' or move.location_dest_id.usage == 'internal':
                    continue
                avail = self.env['stock.quant']._get_available_quantity(
                    move.product_id, move.location_id,
                    lot_id=move.lot_ids[:1] if move.lot_ids else None, strict=False)
                demand = move.quantity if hasattr(move, 'quantity') else move.product_uom_qty
                if avail < demand:
                    msg = _(
                        'Negative Stock Blocked!\n'
                        'Product: %(product)s\nAvailable: %(available)s\n'
                        'Requested: %(demand)s\nLocation: %(location)s',
                        product=move.product_id.display_name, available=avail,
                        demand=demand, location=move.location_id.complete_name)
                    if mode == 'hard' and not bypass:
                        raise UserError(msg)
                    else:
                        _logger.warning('Neg stock: %s avail=%s demand=%s @ %s',
                            move.product_id.display_name, avail, demand,
                            move.location_id.complete_name)
        return super()._action_done(**kwargs)
