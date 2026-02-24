import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_below_cost_lines(self):
        """Return order lines where price_unit is below cost and not yet approved."""
        self.ensure_one()
        below_cost = self.env['sale.order.line']

        for line in self.order_line:
            if line.price_override_approved:
                continue
            if line.display_type or not line.product_id:
                continue

            unit_cost = line.product_id.standard_price or 0.0
            unit_price = line.price_unit or 0.0

            if unit_cost > 0 and unit_price < unit_cost:
                below_cost |= line

        return below_cost

    def action_confirm(self):
        for order in self:
            below_cost_lines = order._get_below_cost_lines()
            if below_cost_lines:
                line_details = []
                for line in below_cost_lines:
                    cost = line.product_id.standard_price
                    price = line.price_unit
                    name = line.product_id.display_name
                    line_details.append(
                        '%s: Unit Price %.2f — Cost Price %.2f' % (
                            name, price, cost,
                        )
                    )

                wizard = self.env['price.override.wizard'].create({
                    'sale_order_id': order.id,
                    'line_info': '\n'.join(line_details),
                })
                return {
                    'name': 'Price Below Cost — Authorization Required',
                    'type': 'ir.actions.act_window',
                    'res_model': 'price.override.wizard',
                    'res_id': wizard.id,
                    'view_mode': 'form',
                    'target': 'new',
                }

        return super().action_confirm()