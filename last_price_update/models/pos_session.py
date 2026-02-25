# -*- coding: utf-8 -*-
from odoo import models, api


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def get_last_customer_prices(self, partner_id, product_ids):
        """RPC method called from POS frontend.
        Returns dict {product_id: last_price} for the given
        partner and list of product IDs.
        Searches both Sale Orders and POS Orders."""
        SaleOrder = self.env['sale.order']
        result = {}
        for pid in product_ids:
            price = SaleOrder._get_last_price(partner_id, pid)
            if price is not None:
                result[pid] = price
        return result
