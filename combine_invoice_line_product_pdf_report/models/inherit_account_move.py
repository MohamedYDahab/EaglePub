from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'


    @api.depends('invoice_line_ids', 'invoice_line_ids.product_id', 'invoice_line_ids.quantity','invoice_line_ids.tax_ids' , 'invoice_line_ids.price_unit')
    def compute_combined_lines(self):
        for move in self:
            combined_lines = {}
            for line in move.invoice_line_ids:
                key = line.product_id.id
                if key not in combined_lines:
                    combined_lines[key] = {
                        'product_id': line.product_id.name,
                        'tax_ids' : "",
                        'quantity_sum': 0.0,
                        'price_unit_avg': 0.0,
                    }
                combined_lines[key]['quantity_sum'] += line.quantity
                combined_lines[key]['price_unit_avg'] += line.price_unit
                combined_lines[key]['tax_ids'] = line.tax_ids.name

            # Create the new combined lines
            combined_line_objs = []
            for key, values in combined_lines.items():
                avg_price_unit = values['price_unit_avg'] / combined_lines[key]['quantity_sum']
                combined_line_objs.append({
                    'product_id': values['product_id'],
                    'quantity': values['quantity_sum'],
                    'price_unit': avg_price_unit,
                    'tax_ids': values['tax_ids'],
                    'price_total' : values['quantity_sum'] * avg_price_unit
                })

            # Update the computed field
            return combined_line_objs




