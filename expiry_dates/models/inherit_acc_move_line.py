from odoo import models, fields, api, _
import datetime


class InheritAccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    lot_name = fields.Char(string='Lot', compute='compute_lot')
    expiration_date = fields.Char(string='Expiry Date', compute='compute_lot')
    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict')
    cost_price = fields.Float(string="Cost Price", related='product_id.standard_price')
    total_cost = fields.Float(string="Total Cost Price", compute='compute_total_cost')
    is_bonus = fields.Boolean(string='Is Bonus')

    def compute_lot(self):
        for rec in self:
            stock_domain = [('origin', '=', rec.move_id.invoice_origin)]
            PO_group = self.env['purchase.order'].read_group(domain=[('name', '=', rec.move_id.invoice_origin)],
                                                             fields=['name'], groupby=['name'])
            SO_group = self.env['sale.order'].read_group(domain=[('name', '=', rec.move_id.invoice_origin)],
                                                         fields=['name'], groupby=['name'])
            SP_search = self.env['stock.picking'].search([('origin', '=', rec.move_id.invoice_origin)])

            lot_list = []
            expiry_list = []
            str_list = []

            if SP_search and PO_group:
                for stock_move_lines in SP_search.move_ids_without_package:
                    if stock_move_lines.product_id.id == rec.product_id.id:
                        if stock_move_lines.quantity_done == rec.quantity:
                            for lots in stock_move_lines.lot_ids:
                                lot_list.append(lots.name)
                                expiry_list.append(lots.expiration_date)
                                lot_list = list(dict.fromkeys(lot_list))
                                expiry_list = list(dict.fromkeys(expiry_list))
                                rec.lot_name = lot_list
                            for dates in expiry_list:
                                if dates:
                                    str_date = datetime.datetime.strftime(dates, '%m/%y')
                                    str_list.append(str_date)
                                    str_list = list(dict.fromkeys(str_list))
                                    rec.expiration_date = str_list
                                else:
                                    rec.expiration_date = ''


            elif SP_search and SO_group:
                for stock_move_lines in SP_search.move_ids_without_package:
                    if stock_move_lines.product_id.id == rec.product_id.id:
                        if stock_move_lines.quantity_done == rec.quantity:
                            for lots in stock_move_lines.lot_ids:
                                lot_list.append(lots.name)
                                expiry_list.append(lots.expiration_date)
                                rec.lot_name = lot_list
                            for dates in expiry_list:
                                if dates:
                                    str_date = datetime.datetime.strftime(dates, '%m/%y')
                                    str_list.append(str_date)
                                    rec.expiration_date = str_list
                                else:
                                    rec.expiration_date = ''



            else:
                rec.lot_name = ''
                rec.expiration_date = ''

    def compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.cost_price * rec.quantity
