from odoo import models, fields


class NegStockWarningWizard(models.TransientModel):
    _name = 'neg.stock.warning.wizard'
    _description = 'Negative Stock Warning Confirmation'

    order_ids = fields.Many2many(
        'sale.order', string="Orders", required=True,
    )
    message = fields.Text(
        string="Shortages", readonly=True,
    )

    def action_confirm(self):
        """Proceed with the confirmation the user was just warned about."""
        self.ensure_one()
        orders = self.order_ids
        # Recomputed rather than reused so the chatter note reflects stock as
        # it stands now, not as it stood when the dialog opened.
        orders._neg_stock_post_warning(orders._neg_stock_issues())
        return orders.with_context(skip_neg_stock_check=True).action_confirm()
