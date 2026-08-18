import logging
from odoo import models, _
from odoo.exceptions import UserError

from . import neg_stock_settings as settings

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, **kwargs):
        if (settings.flag(self.env, 'enabled')
                and settings.flag(self.env, 'stock_enabled')):
            mode = settings.param(self.env, 'mode', 'hard')
            qty_type = settings.param(self.env, 'qty_type', 'available')
            bypass = self.env.user.has_group(
                'negative_stock_restriction.group_bypass_negative_stock'
            )

            for move in self:
                if not move.product_id or move.product_id.type != 'product':
                    continue

                # Only check outgoing moves (internal → not-internal)
                if move.location_id.usage != 'internal' or \
                   move.location_dest_id.usage == 'internal':
                    continue

                # ── Per-product exception ──────────────────────────────
                if move.product_id.allow_negative_stock or \
                   move.product_id.product_tmpl_id.allow_negative_stock:
                    continue

                # ── Per-category exception ─────────────────────────────
                if move.product_id.categ_id and \
                   move.product_id.categ_id.allow_negative_stock:
                    continue

                # ── Per-warehouse exception ────────────────────────────
                warehouse = move.location_id.warehouse_id
                if warehouse and warehouse.allow_negative_stock:
                    continue

                # ── Get quantity based on configured type ──────────────
                if qty_type == 'on_hand':
                    quants = self.env['stock.quant'].search([
                        ('product_id', '=', move.product_id.id),
                        ('location_id', '=', move.location_id.id),
                    ])
                    avail = sum(quants.mapped('quantity'))
                elif qty_type == 'forecast':
                    avail_qty = self.env['stock.quant'] \
                        ._get_available_quantity(
                            move.product_id, move.location_id,
                            lot_id=move.lot_ids[:1] if move.lot_ids
                            else None, strict=False)
                    incoming = sum(self.env['stock.move'].search([
                        ('product_id', '=', move.product_id.id),
                        ('location_dest_id', '=', move.location_id.id),
                        ('state', 'in',
                         ('waiting', 'confirmed', 'assigned')),
                        ('id', '!=', move.id),
                    ]).mapped('product_uom_qty'))
                    avail = avail_qty + incoming
                else:
                    # Default: available
                    avail = self.env['stock.quant'] \
                        ._get_available_quantity(
                            move.product_id, move.location_id,
                            lot_id=move.lot_ids[:1] if move.lot_ids
                            else None, strict=False)
                demand = move.quantity if hasattr(move, 'quantity') else \
                    move.product_uom_qty

                if avail < demand:
                    msg = _(
                        "Negative Stock Blocked!\n"
                        "Product: %(product)s\n"
                        "Available: %(available)s\n"
                        "Requested: %(demand)s\n"
                        "Location: %(location)s\n\n",
                        product=move.product_id.display_name,
                        available=avail,
                        demand=demand,
                        location=move.location_id.complete_name,
                    )
                    if mode == 'hard' and not bypass:
                        raise UserError(msg)
                    else:
                        _logger.warning(
                            'Neg stock: %s avail=%s demand=%s @ %s',
                            move.product_id.display_name,
                            avail, demand,
                            move.location_id.complete_name,
                        )

        return super()._action_done(**kwargs)
