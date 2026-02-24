# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_update_last_prices(self):
        """Button action: update each SO line price to the last price
        charged to the same customer for the same product.
        Searches both confirmed Sale Orders and completed POS Orders.
        If no previous order found, keeps Odoo's default price."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(
                _('Please select a customer first.\n'
                  'يرجى اختيار العميل أولاً'))

        updated = 0
        for line in self.order_line.filtered(lambda l: l.product_id):
            price = self._get_last_price(
                self.partner_id.id, line.product_id.id,
                exclude_so_id=self.id)
            if price is not None:
                line.price_unit = price
                updated += 1

        if updated == 0:
            raise UserError(
                _('No previous prices found for this customer.\n'
                  'لم يتم العثور على أسعار سابقة لهذا العميل'))

    @api.model
    def _get_last_price(self, partner_id, product_id,
                        exclude_so_id=False):
        """Find the most recent price for partner + product.
        Searches both Sale Orders and POS Orders, returns the
        most recent one. Returns None if no history found."""
        best_date = False
        best_price = None

        # ── Search confirmed Sale Order lines ──
        so_domain = [
            ('order_id.partner_id', '=', partner_id),
            ('order_id.state', 'in', ['sale', 'done']),
            ('product_id', '=', product_id),
        ]
        if exclude_so_id:
            so_domain.append(('order_id', '!=', exclude_so_id))

        so_line = self.env['sale.order.line'].sudo().search(
            so_domain, order='create_date desc', limit=1)
        if so_line:
            best_date = so_line.create_date
            best_price = so_line.price_unit

        # ── Search completed POS Order lines ──
        try:
            pos_line = self.env['pos.order.line'].sudo().search([
                ('order_id.partner_id', '=', partner_id),
                ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
                ('product_id', '=', product_id),
            ], order='create_date desc', limit=1)
            if pos_line:
                if not best_date or pos_line.create_date > best_date:
                    best_price = pos_line.price_unit
        except Exception:
            pass  # POS module tables might not exist

        return best_price
