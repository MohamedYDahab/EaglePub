from odoo import models, fields, api, _
import datetime


class SaleOrderLineInheritance(models.Model):
    _inherit = 'sale.order.line'

# Passs Value From SO Line to Invoice Line
    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLineInheritance, self)._prepare_invoice_line()
        res.update({
            'so_name': self.order_id,
        })
        return res



class AccountOrderLineInheritance(models.Model):
    _inherit = 'account.move.line'


    so_name = fields.Many2one('sale.order',string='sale order line')
    expiry_date = fields.Char(string="Product Name", compute="computed_expiry")


    def computed_expiry(self):

        #Get Stock Moves Related to SaleOrder Using ORM Search Method
        move_line = self.env['stock.picking'].search([('origin','=',self.so_name.name)])
        mapped_lines = move_line.mapped('move_line_ids_without_package')
        list_dates = []
        list_names = []
        list_product = []
        list_dict = {}
        final = []



        #Get Lot Name and Expiry Date from Stock Move
        #Loop in Lots inside Stock Move to Get Required Data
        if mapped_lines:
            for mapped in mapped_lines.lot_id:
                if mapped.expiration_date:
                    date = mapped.expiration_date.date()
                    str_date = date.strftime('%m/%Y')
                    name = mapped.name
                    product = mapped.product_id.name

                    list_dates.append(str_date)
                    list_names.append(name)
                    list_product.append(product)

                    list_dict['dates'] = list_dates
                    list_dict['names'] = list_names
                    list_dict['products'] = list_product
                else:
                    for rec in self:
                        rec.expiry_date = []
        else:
            for rec in self:
                rec.expiry_date = []


        for rec in self:

            def list_duplicates_of(seq, item):
                start_at = -1
                locs = []
                while True:
                    try:
                        loc = seq.index(item, start_at + 1)
                    except ValueError:
                        break
                    else:
                        locs.append(loc)
                        start_at = loc
                return locs

            index_list = list_duplicates_of(list_product, rec.product_id.name)



            for indexes in index_list:
                # names = ' Lot No. : '+ list_dict['names'][indexes] + 'Product : ' + list_dict['products'][indexes] + '  Expiray: ' + list_dict['dates'][indexes]
                # names = ' Lot : '+ list_dict['names'][indexes] +  ' | Expiry: ' + list_dict['dates'][indexes]
                names = list_dict['names'][indexes] + '|Expiry:' + list_dict['dates'][indexes]

                final.append(names)
                last_name = final[min(index_list):max(index_list)+1]
                if last_name:
                    rec.expiry_date = last_name
                else:
                    rec.expiry_date = []

