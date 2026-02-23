# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # Manual lot selection for direct invoices
    manual_lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        relation='account_move_line_stock_lot_rel',
        column1='move_line_id',
        column2='lot_id',
        string='Manual Lots',
        domain="[('product_id', '=', product_id)]",
        help='Manually select lots for direct invoices',
    )

    # Computed fields that combine automatic + manual lots
    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        string='Lot/Serial Numbers',
        compute='_compute_lot_expiry_info',
        help='Lot/Serial numbers from related stock moves or manual selection',
    )
    lot_names_display = fields.Char(
        string='Lots',
        compute='_compute_lot_expiry_info',
        help='Comma-separated list of lot/serial names',
    )
    expiry_dates_display = fields.Char(
        string='Expiry Dates',
        compute='_compute_lot_expiry_info',
        help='Comma-separated list of expiry dates',
    )
    has_lot_tracking = fields.Boolean(
        string='Has Lot Tracking',
        compute='_compute_lot_expiry_info',
        help='Indicates if the product has lot/serial tracking',
    )
    is_direct_invoice = fields.Boolean(
        string='Is Direct Invoice',
        compute='_compute_is_direct_invoice',
        help='True if this line is not linked to a sale or purchase order',
    )

    ref = fields.Char(
        string="Lot Reference",
        compute='_compute_lot_expiry_info',
    )

    @api.depends('sale_line_ids', 'purchase_line_id')
    def _compute_is_direct_invoice(self):
        """Check if this is a direct invoice (not from SO/PO)"""
        for line in self:
            line.is_direct_invoice = not line.sale_line_ids and not line.purchase_line_id

    @api.depends(
        'sale_line_ids', 'sale_line_ids.move_ids', 'sale_line_ids.move_ids.lot_ids',
        'purchase_line_id', 'purchase_line_id.move_ids', 'purchase_line_id.move_ids.lot_ids',
        'manual_lot_ids'
    )
    def _compute_lot_expiry_info(self):
        for line in self:
            lots = self.env['stock.lot']

            # From SO
            if line.sale_line_ids:
                for sale_line in line.sale_line_ids:
                    lots |= sale_line.move_ids.mapped('lot_ids')

            # From PO
            if line.purchase_line_id and line.purchase_line_id.move_ids:
                lots |= line.purchase_line_id.move_ids.mapped('lot_ids')

            # Manual lots
            lots |= line.manual_lot_ids

            line.lot_ids = lots
            line.has_lot_tracking = bool(lots)

            if lots:
                # Lot names
                line.lot_names_display = ', '.join(lots.mapped('name'))

                # Lot references ✅
                refs = lots.mapped('ref')
                line.ref = ', '.join(filter(None, refs))

                # Expiry dates
                expiry_dates = [
                    lot.expiration_date.strftime('%Y-%m-%d')
                    for lot in lots
                    if lot.expiration_date
                ]
                line.expiry_dates_display = ', '.join(expiry_dates)
            else:
                line.lot_names_display = ''
                line.expiry_dates_display = ''
                line.ref = ''


    def get_lot_expiry_data(self):
        """
        Returns a list of dictionaries with lot and expiry information.
        Useful for custom reports or API access.
        """
        self.ensure_one()
        result = []
        for lot in self.lot_ids:
            result.append({
                'lot_name': lot.name,
                'expiration_date': lot.expiration_date,
                'expiry_date_formatted': lot.expiration_date.strftime('%Y-%m-%d') if lot.expiration_date else '',
            })
        return result