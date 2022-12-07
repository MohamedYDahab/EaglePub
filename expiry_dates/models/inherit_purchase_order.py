from odoo import api, fields, models


class InheritPurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    is_bonus = fields.Boolean(default=False, string='Is Bonus')
    discount = fields.Float(string="Discount", default=0.0, compute='compute_discount')

    @api.depends('is_bonus')
    def compute_discount(self):
        for line in self:
            if line.is_bonus == True:
                line.discount = 100
            else:
                line.discount = 0

    def _prepare_compute_all_values(self):
        # Hook method to returns the different argument values for the
        # compute_all method, due to the fact that discounts mechanism
        # is not implemented yet on the purchase orders.
        # This method should disappear as soon as this feature is
        # also introduced like in the sales module.
        self.ensure_one()
        if self.is_bonus == True:
            price_unit = self.price_unit * 0
        else:
            price_unit = self.price_unit

        return {
            'price_unit': price_unit,
            'currency': self.order_id.currency_id,
            'quantity': self.product_qty,
            'product': self.product_id,
            'partner': self.order_id.partner_id,
        }



    def _prepare_account_move_line(self, move=False):
        self.ensure_one()
        aml_currency = move and move.currency_id or self.currency_id

        date = move and move.date or fields.Date.today()
        res = {
            'display_type': self.display_type,
            'sequence': self.sequence,
            'name': '%s: %s' % (self.order_id.name, self.name),
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'price_unit': self.currency_id._convert(self.price_unit, aml_currency, self.company_id, date, round=False),
            'tax_ids': [(6, 0, self.taxes_id.ids)],
            'analytic_account_id': self.account_analytic_id.id,
            'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
            'purchase_line_id': self.id,
            'is_bonus': self.is_bonus,
            'discount': self.discount,
        }
        if not move:
            return res

        if self.currency_id == move.company_id.currency_id:
            currency = False
        else:
            currency = move.currency_id

        res.update({
            'move_id': move.id,
            'currency_id': currency and currency.id or False,
            'date_maturity': move.invoice_date_due,
            'partner_id': move.partner_id.id,
        })
        return res
