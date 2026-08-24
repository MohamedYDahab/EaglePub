from datetime import datetime, time

from odoo import models

# What a till order has to be for the money to count as taken.
SOLD_STATES = ('paid', 'done')


class EaglepubCommissionComputeWizard(models.TransientModel):
    _inherit = 'eaglepub.commission.compute.wizard'

    def _collect_for(self, plan, user):
        """Add till sales to whatever the base module already found.

        A salesperson who sells over the counter in the morning and on invoice
        in the afternoon should be paid for both, so this adds to the result
        rather than replacing it.
        """
        lines = super()._collect_for(plan, user)
        if plan.include_pos:
            lines = lines + self._collect_pos_orders(plan, user)
        return lines

    def _collect_pos_orders(self, plan, user):
        """Commissionable lines from the point of sale.

        Basis is deliberately ignored here. A till order is rung up, paid and
        settled in one motion, so 'confirmed', 'invoiced' and 'paid' are the
        same instant - there is nothing to distinguish.
        """
        orders = self.env['pos.order'].search([
            ('state', 'in', SOLD_STATES),
            ('user_id', '=', user.id),
            ('date_order', '>=', datetime.combine(self.date_from, time.min)),
            ('date_order', '<=', datetime.combine(self.date_to, time.max)),
            ('company_id', '=', self.company_id.id),
        ])

        vals = []
        for order in orders:
            for line in order.lines:
                if not line.product_id:
                    continue
                rule = plan.rule_for_product(line.product_id)
                if not rule:
                    continue
                # A POS refund carries negative quantities and subtotals of its
                # own, so it subtracts without any sign handling here.
                base = self._base_of(
                    plan, line.product_id, line.price_subtotal, line.qty)
                vals.append({
                    'date': order.date_order.date(),
                    'reference': order.name,
                    'partner_id': order.partner_id.id,
                    'product_id': line.product_id.id,
                    'quantity': line.qty,
                    'pos_order_id': order.id,
                    'base_amount': base,
                    'rate': rule.rate,
                    'amount': base * rule.rate / 100.0,
                })
        return vals
