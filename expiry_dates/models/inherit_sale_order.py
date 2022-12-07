from odoo import api, fields, models




class InheritSaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_bonus = fields.Boolean(default=False, string='Is Bonus')
    discount = fields.Float(string="Discount", default=0.0, compute='compute_discount')



    # Discount Button already Exists in SO Line, added to be computed using the following Function
    @api.depends('is_bonus')
    def compute_discount(self):
        for line in self:
            if line.is_bonus == True:
                line.discount = 100
            else:
                line.discount = 0


    # Prepare Invoice Fuction is inherited to add Is Bonus field and its Value to Invoice Line
    def _prepare_invoice_line(self, **optional_values):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        :param optional_values: any parameter that should be added to the returned invoice line
        """
        self.ensure_one()
        res = {
            'display_type': self.display_type,
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'discount': self.discount,
            'price_unit': self.price_unit,
            'tax_ids': [(6, 0, self.tax_id.ids)],
            'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
            'sale_line_ids': [(4, self.id)],
            'is_bonus': self.is_bonus,
        }
        if self.order_id.analytic_account_id and not self.display_type:
            res['analytic_account_id'] = self.order_id.analytic_account_id.id
        if optional_values:
            res.update(optional_values)
        if self.display_type:
            res['account_id'] = False
        return res
