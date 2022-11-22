from odoo import models, fields, api, _
from datetime import date



class AccountOrderLineInheritance(models.Model):
    _inherit = 'account.move.line'


    expiry_date = fields.Char(string="Product Name", compute='get_values')
    source_document = fields.Char(string='Source Doc.', compute='get_values')
    product_id = fields.Many2one('product.product', string='Product', ondelete='restrict')
    cost_price = fields.Float(string="Cost Price", related='product_id.standard_price')
    reference = fields.Char(string="Reference", compute='get_values')
    lot_name = fields.Char(string="Lot", compute='get_values')


    def get_values(self):
        for rec in self:
            PO_search = self.env['purchase.order'].search([('name', '=', rec.move_id.invoice_origin)])
            SO_search = self.env['sale.order'].search([('name', '=', rec.move_id.invoice_origin)])
            SP_search = self.env['stock.picking'].search([('origin', '=', rec.move_id.invoice_origin)])
            SM_search = self.env['stock.move'].search([('origin', '=', rec.move_id.invoice_origin)])

            if rec.move_id.invoice_origin:
                SP_move_line = SP_search.move_ids_without_package
                referenc_list = []
                for moves in SP_move_line:
                    referenc_list.append(moves.reference)

                rec.reference = referenc_list[0]
            else:
                rec.reference = ''

            if PO_search:
                rec.source_document = PO_search.name

            elif SO_search:
                rec.source_document = SO_search.name
            else:
                rec.source_document = ''

            if SM_search.move_line_ids and rec.move_id.invoice_origin:
                lot_list = []
                expiry_list = []
                str_date_list = []
                for lines in SM_search.move_line_ids:
                    if lines.lot_id and lines.lot_id.expiration_date:
                        lot_list.append(lines.lot_id.name)
                        expiry_list.append(lines.lot_id.expiration_date.date())
                        for dates in expiry_list:
                            str_date = date.strftime(dates, "%m/%Y")
                        str_date_list.append(str_date)
                        lot_list = list(dict.fromkeys(lot_list))
                        rec.lot_name = lot_list
                        # str_date = date.strftime(pre_date, "%m/%Y")
                        str_date_list = list(dict.fromkeys(str_date_list))
                        rec.expiry_date = str_date_list
                    else:
                        rec.expiry_date = ''
            else:
                rec.lot_name = ''
                rec.expiry_date = ''


##############################

##########################

##########################