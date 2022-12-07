from odoo import models, fields, api, _
from datetime import datetime, date


class InheritStockAdjustment(models.Model):
    _inherit = 'stock.quant'

    lot_expiry = fields.Datetime(string='Expiry Date',compute='get_expiry' ,readonly=False)
    lot_id = fields.Many2one(
        'stock.production.lot', 'Lot/Serial Number', index=True,
        ondelete='restrict', check_company=True,
        domain=lambda self: self._domain_lot_id(), required=True)


    @api.model
    def _get_inventory_fields_create(self):
        """ Returns a list of fields user can edit when he want to create a quant in `inventory_mode`.
        """
        return ['product_id', 'location_id', 'lot_id', 'package_id', 'owner_id','lot_expiry'] + self._get_inventory_fields_write()


    @api.depends('lot_id')
    def get_expiry(self):
        for rec in self:
            rec.lot_expiry = rec.lot_id.expiration_date

    @api.onchange('lot_expiry')
    def set_expiry(self):
        adjust_obj = self.env['stock.production.lot']
        search_obj = adjust_obj.search([('name','=',self.lot_id.name)])
        search_obj.expiration_date = self.lot_expiry
        self.lot_expiry = search_obj.expiration_date




class InheritStockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    expiration_date = fields.Datetime(string='Expiry Date')



