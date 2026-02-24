# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # ── Manual lot selection for direct invoices (not linked to SO/PO) ──
    manual_lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        relation='account_move_line_manual_lot_rel',
        column1='move_line_id',
        column2='lot_id',
        string='Manual Lots',
        domain="[('product_id', '=', product_id)]",
        help='Manually select lots for direct invoices not linked to SO/PO',
    )

    # ── Computed lot/expiry fields ──
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
    # NOTE: renamed from `ref` to `lot_ref` to avoid overriding the base
    # account.move.line `ref` field which is used for payment references.
    lot_ref = fields.Char(
        string='Lot Reference',
        compute='_compute_lot_expiry_info',
        help='Comma-separated lot internal references',
    )
    has_lot_tracking = fields.Boolean(
        string='Has Lot Tracking',
        compute='_compute_lot_expiry_info',
    )
    is_direct_invoice = fields.Boolean(
        string='Is Direct Invoice',
        compute='_compute_is_direct_invoice',
        help='True if this line is not linked to a sale or purchase order',
    )

    @api.depends('sale_line_ids', 'purchase_line_id')
    def _compute_is_direct_invoice(self):
        for line in self:
            line.is_direct_invoice = (
                not line.sale_line_ids and not line.purchase_line_id
            )

    @api.depends(
        'sale_line_ids', 'sale_line_ids.move_ids', 'sale_line_ids.move_ids.lot_ids',
        'purchase_line_id', 'purchase_line_id.move_ids', 'purchase_line_id.move_ids.lot_ids',
        'manual_lot_ids',
    )
    def _compute_lot_expiry_info(self):
        for line in self:
            lots = self.env['stock.lot']

            # Lots from Sale Order deliveries
            if line.sale_line_ids:
                for sale_line in line.sale_line_ids:
                    lots |= sale_line.move_ids.lot_ids

            # Lots from Purchase Order receipts
            if line.purchase_line_id and line.purchase_line_id.move_ids:
                lots |= line.purchase_line_id.move_ids.lot_ids

            # Manual lots for direct invoices
            if line.manual_lot_ids:
                lots |= line.manual_lot_ids

            line.lot_ids = lots
            line.has_lot_tracking = bool(lots)

            if lots:
                line.lot_names_display = ', '.join(lots.mapped('name'))

                refs = lots.mapped('ref')
                line.lot_ref = ', '.join(r for r in refs if r)

                expiry_dates = [
                    lot.expiration_date.strftime('%Y-%m-%d')
                    for lot in lots
                    if lot.expiration_date
                ]
                line.expiry_dates_display = ', '.join(expiry_dates)
            else:
                line.lot_names_display = ''
                line.expiry_dates_display = ''
                line.lot_ref = ''

    def action_view_lots(self):
        """Button action: open lots/serials in a popup tree view."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'target': 'new',
            'name': _('Lots / Serials'),
            'view_mode': 'tree',
            'view_id': self.env.ref(
                'lots_serials_in_invoice_lines.stock_lot_custom_tree'
            ).id,
            'res_model': 'stock.lot',
            'domain': [('id', 'in', self.lot_ids.ids)],
        }

    def get_lot_expiry_data(self):
        """Returns a list of dicts with lot and expiry info.
        Useful for custom reports or API access."""
        self.ensure_one()
        return [
            {
                'lot_name': lot.name,
                'lot_ref': lot.ref or '',
                'expiration_date': lot.expiration_date,
                'expiry_date_formatted': (
                    lot.expiration_date.strftime('%Y-%m-%d')
                    if lot.expiration_date else ''
                ),
            }
            for lot in self.lot_ids
        ]
