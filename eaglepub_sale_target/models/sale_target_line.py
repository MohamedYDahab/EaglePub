from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


class SaleTargetLine(models.Model):
    _name = 'sale.target.line'
    _description = 'Sales Target Line'

    target_id = fields.Many2one(
        'sale.target',
        string='Sales Target',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )
    measured_on = fields.Selection(
        [
            ('sale_order', 'Sale Orders'),
            ('invoice', 'Invoices'),
        ],
        string='Measured On',
        required=True,
        default='sale_order',
        help='Sale Orders: achievement is read from confirmed sale orders '
             '(state Sales Order or Locked).\n'
             'Invoices: achievement is read from posted customer invoices, '
             'net of credit notes.',
    )
    target_qty = fields.Float(
        string='Target Qty',
        digits='Product Unit of Measure',
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
    )
    price_unit = fields.Float(
        string='Sales Price',
        digits='Product Price',
        compute='_compute_price_unit',
        store=True,
        readonly=False,
        help='Defaults to the product sales price and can be overridden, for '
             'instance when the target assumes a negotiated price.',
    )
    amount_untaxed = fields.Monetary(
        string='Total Amount',
        currency_field='currency_id',
        compute='_compute_amount_untaxed',
        store=True,
        help='Target quantity valued at the line price, excluding tax. What '
             'this target is worth if it is fully achieved.',
    )
    currency_id = fields.Many2one(
        related='target_id.currency_id',
        store=True,
    )

    achieved_qty = fields.Float(
        string='Achieved Qty',
        compute='_compute_achieved',
        digits='Product Unit of Measure',
    )
    achieved_amount = fields.Monetary(
        string='Achieved Amount',
        compute='_compute_achieved',
        currency_field='currency_id',
        help='Value actually sold, excluding tax. Informational: progress is '
             'measured on quantity.',
    )
    achieved_percentage = fields.Float(
        string='Achieved Percentage',
        compute='_compute_achieved',
    )
    remaining = fields.Float(
        string='Remaining Qty',
        compute='_compute_achieved',
        digits='Product Unit of Measure',
    )
    current_stock_qty = fields.Float(
        string='Current Stock',
        compute='_compute_current_stock_qty',
        digits='Product Unit of Measure',
        help='Quantity on hand right now, expressed in this line unit of '
             'measure. This is a live figure and is not limited to the target '
             'period.',
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    @api.depends('product_id')
    def _compute_price_unit(self):
        for line in self:
            # lst_price rather than list_price: it carries the variant extra.
            line.price_unit = line.product_id.lst_price if line.product_id else 0.0

    @api.depends('target_qty', 'price_unit')
    def _compute_amount_untaxed(self):
        for line in self:
            line.amount_untaxed = line.target_qty * line.price_unit

    @api.depends('product_id', 'measured_on', 'target_qty',
                 'target_id.date_start', 'target_id.date_end',
                 'target_id.assign_to', 'target_id.salesperson_id',
                 'target_id.team_id', 'target_id.company_id')
    def _compute_achieved(self):
        for line in self:
            target = line.target_id
            if not (line.product_id and target.date_start and target.date_end):
                line.achieved_amount = 0.0
                line.achieved_qty = 0.0
                line.achieved_percentage = 0.0
                line.remaining = 0.0
                continue

            if line.measured_on == 'invoice':
                achieved = line._get_invoiced_achievement()
            else:
                achieved = line._get_ordered_achievement()
            line.achieved_amount, line.achieved_qty = achieved

            line.achieved_percentage = (
                (line.achieved_qty / line.target_qty) * 100.0
                if line.target_qty else 0.0
            )
            line.remaining = max(line.target_qty - line.achieved_qty, 0.0)

    @api.depends('product_id', 'uom_id')
    def _compute_current_stock_qty(self):
        for line in self:
            product = line.product_id
            if not product:
                line.current_stock_qty = 0.0
                continue
            on_hand = product.qty_available
            to_uom = line.uom_id or product.uom_id
            if to_uom and to_uom != product.uom_id:
                # Odoo 19 dropped uom category_id in favour of a unit
                # hierarchy; raise_if_failure=False leaves the figure in the
                # product unit when the two are unrelated.
                on_hand = product.uom_id._compute_quantity(
                    on_hand, to_uom, raise_if_failure=False)
            line.current_stock_qty = on_hand

    def _report_assignee_name(self):
        """Who this line's target belongs to, salesperson or team."""
        self.ensure_one()
        target = self.target_id
        if target.assign_to == 'team':
            return target.team_id.display_name or ''
        return target.salesperson_id.display_name or ''

    # ─────────────────── Achievement ───────────────────

    def _get_assignee_domain(self, user_field, team_field):
        """Restrict achievement to the salesperson or team the target is assigned to."""
        self.ensure_one()
        target = self.target_id
        if target.assign_to == 'salesperson' and target.salesperson_id:
            return [(user_field, '=', target.salesperson_id.id)]
        elif target.assign_to == 'team' and target.team_id:
            return [(team_field, '=', target.team_id.id)]
        return []

    def _get_ordered_domain(self):
        """Sale order lines counted toward this target line."""
        self.ensure_one()
        target = self.target_id
        domain = [
            ('product_id', '=', self.product_id.id),
            ('order_id.state', 'in', ['sale', 'done']),
            ('order_id.date_order', '>=', fields.Datetime.to_datetime(target.date_start)),
            ('order_id.date_order', '<', fields.Datetime.to_datetime(target.date_end) + relativedelta(days=1)),
        ]
        domain.append(('order_id.company_id', '=', target.company_id.id))
        domain += self._get_assignee_domain('order_id.user_id', 'order_id.team_id')
        return domain

    def _get_ordered_achievement(self):
        """Achievement read from confirmed Sale Orders. Returns (amount, qty)."""
        self.ensure_one()
        order_lines = self.env['sale.order.line'].search(self._get_ordered_domain())
        # price_subtotal excludes tax, matching the untaxed target amount.
        return (
            sum(order_lines.mapped('price_subtotal')),
            sum(order_lines.mapped('product_uom_qty')),
        )

    def _get_invoiced_domain(self):
        """Invoice lines counted toward this target line.

        Covers every posted customer invoice for the product, whether or not it
        originates from a sale order. Credit notes are included so they can be
        subtracted, keeping a return from inflating a target.
        """
        self.ensure_one()
        target = self.target_id
        domain = [
            ('product_id', '=', self.product_id.id),
            ('parent_state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('display_type', '=', 'product'),
            ('move_id.invoice_date', '>=', target.date_start),
            ('move_id.invoice_date', '<=', target.date_end),
        ]
        domain.append(('move_id.company_id', '=', target.company_id.id))
        domain += self._get_assignee_domain('move_id.invoice_user_id', 'move_id.team_id')
        return domain

    def _get_invoiced_achievement(self):
        """Achievement read from posted customer invoices. Returns (amount, qty)."""
        self.ensure_one()
        amount = qty = 0.0
        for aml in self.env['account.move.line'].search(self._get_invoiced_domain()):
            sign = -1.0 if aml.move_id.move_type == 'out_refund' else 1.0
            # price_subtotal excludes tax, matching the untaxed target amount.
            amount += sign * aml.price_subtotal
            qty += sign * aml.quantity
        return amount, qty

    # ─────────────────── Drill-down ───────────────────

    def action_view_source_documents(self):
        """Open the documents this line's achievement was measured from.

        Reuses the very domains the achievement figures are computed from, so
        the drill-down can never show a different set of documents than the
        numbers were built on.
        """
        self.ensure_one()
        if self.measured_on == 'invoice':
            moves = self.env['account.move.line'].search(
                self._get_invoiced_domain()).move_id
            return {
                'type': 'ir.actions.act_window',
                'name': _('Invoices - %s', self.product_id.display_name),
                'res_model': 'account.move',
                'view_mode': 'list,form',
                'domain': [('id', 'in', moves.ids)],
                'context': {'create': False},
            }

        orders = self.env['sale.order.line'].search(
            self._get_ordered_domain()).order_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Orders - %s', self.product_id.display_name),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', orders.ids)],
            'context': {'create': False},
        }
