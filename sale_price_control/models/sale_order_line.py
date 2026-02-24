import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    price_override_approved = fields.Boolean(
        string='Price Override Approved',
        default=False,
        copy=False,
        help='Set to True after password authorization for below-cost prices.',
    )

    @api.onchange('price_unit')
    def _onchange_price_unit_reset_approval(self):
        """Reset price override approval when unit price is changed."""
        if self.price_override_approved:
            self.price_override_approved = False

    @api.onchange('product_id')
    def _onchange_product_reset_approval(self):
        """Reset price override approval when product is changed."""
        if self.price_override_approved:
            self.price_override_approved = False

    def write(self, vals):
        """Also reset approval on direct writes (non-UI changes)."""
        if any(f in vals for f in ('price_unit', 'product_id')):
            if 'price_override_approved' not in vals:
                vals = dict(vals, price_override_approved=False)
        return super().write(vals)