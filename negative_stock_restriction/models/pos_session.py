from odoo import models, api

class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def get_stock_for_products(self, product_ids, location_id=False):
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('negative_stock_restriction.enabled', 'True')
        pos_enabled = ICP.get_param('negative_stock_restriction.pos_enabled', 'True')
        mode = ICP.get_param('negative_stock_restriction.mode', 'hard')
        if enabled != 'True' or pos_enabled != 'True':
            return {'enabled': False, 'mode': mode, 'stock': {}}
        location = False
        if location_id:
            location = self.env['stock.location'].browse(location_id)
        else:
            sess = self.search([('state', '=', 'opened'),
                                ('user_id', '=', self.env.uid)], limit=1)
            if sess and sess.config_id.picking_type_id:
                location = sess.config_id.picking_type_id.default_location_src_id
        result = {}
        for p in self.env['product.product'].browse(product_ids):
            if p.type != 'product':
                result[p.id] = 9999999
                continue
            result[p.id] = self.env['stock.quant']._get_available_quantity(
                p, location, strict=False) if location else p.qty_available
        bypass = self.env.user.has_group('negative_stock_restriction.group_bypass_negative_stock')
        return {'enabled': True, 'mode': mode, 'stock': result, 'bypass': bypass}
