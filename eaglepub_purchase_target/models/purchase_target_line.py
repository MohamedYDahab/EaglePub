from datetime import datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseTargetLine(models.Model):
    _name = 'purchase.target.line'
    _description = 'Purchase Target Line'

    target_id = fields.Many2one(
        'purchase.target',
        string='Purchase Target',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
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
        string='Cost Price',
        digits='Product Price',
        compute='_compute_price_unit',
        store=True,
        readonly=False,
        help='Defaults to this vendor price for the product, falling back to '
             'the product cost. Override it when the target assumes a '
             'negotiated price.',
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

    achieved_amount = fields.Monetary(
        string='Received Amount',
        compute='_compute_achieved',
        currency_field='currency_id',
        help='Value actually received, excluding tax. Informational: progress '
             'is measured on quantity.',
    )
    achieved_qty = fields.Float(
        string='Received Qty',
        compute='_compute_achieved',
        digits='Product Unit of Measure',
    )
    achieved_percentage = fields.Float(
        string='Received Percentage',
        compute='_compute_achieved',
    )
    remaining_qty = fields.Float(
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
    qty_ordered_not_received = fields.Float(
        string='Ordered Not Delivered',
        compute='_compute_qty_ordered_not_received',
        digits='Product Unit of Measure',
        help='Still outstanding on confirmed purchase orders from this vendor: '
             'ordered but not yet received. Like Current Stock this is a live '
             'figure covering every open order, not only those raised inside '
             'the target period.',
    )

    # ── Replenishment alert ──
    # Every input is exposed as its own column: when a buyer disputes an alert,
    # the term that drove it has to be visible rather than inferred.
    monthly_forecast = fields.Float(
        string='Monthly Forecast',
        compute='_compute_replenishment',
        digits='Product Unit of Measure',
        help='Target quantity spread over the length of the target period. A '
             'yearly target of 1200 is a monthly forecast of 100, not 1200.',
    )
    lead_time_days = fields.Integer(
        string='Lead Time (days)',
        compute='_compute_replenishment',
        help="This vendor's lead time for the product, from the vendor pricelist.",
    )
    safety_stock = fields.Float(
        string='Safety Stock',
        compute='_compute_replenishment',
        digits='Product Unit of Measure',
        help='Min Quantity on the reordering rules for this product, summed '
             'across warehouses. Zero where no reordering rule exists.',
    )
    available_qty = fields.Float(
        string='Available',
        compute='_compute_replenishment',
        digits='Product Unit of Measure',
        help='On hand minus quantity already reserved against orders. Reserved '
             'stock cannot cover new demand.',
    )
    replenishment_qty = fields.Float(
        string='To Replenish',
        compute='_compute_replenishment',
        digits='Product Unit of Measure',
        help='(Monthly Forecast x Lead Time in months) + Safety Stock '
             '- Available - Ordered Not Delivered.\n'
             'Above zero means stock runs out before a new order could arrive, '
             'and the figure is how much to order.',
    )
    needs_replenishment = fields.Boolean(
        string='Replenishment Needed',
        compute='_compute_replenishment',
        search='_search_needs_replenishment',
        help='Set when the shortfall exceeds the tolerance configured in '
             'Purchase settings.',
    )
    last_alert_qty = fields.Float(
        string='Last Alerted Shortfall',
        readonly=True, copy=False,
        digits='Product Unit of Measure',
        help='Shortfall at the last notification, used so a line is not '
             'reported again every day at the same severity.',
    )
    last_alert_date = fields.Datetime(
        string='Last Alerted On', readonly=True, copy=False,
    )

    def _period_months(self):
        """Length of the target period in months.

        Measured on the calendar rather than by dividing days, so a month is
        one and a quarter is three regardless of how many days they contain.
        """
        self.ensure_one()
        target = self.target_id
        if not (target.date_start and target.date_end):
            return 0.0
        delta = relativedelta(target.date_end + timedelta(days=1),
                              target.date_start)
        return delta.years * 12 + delta.months + delta.days / 30.0

    @api.depends('product_id', 'uom_id', 'target_qty',
                 'target_id.partner_id', 'target_id.company_id',
                 'target_id.date_start', 'target_id.date_end')
    def _compute_replenishment(self):
        for line in self:
            product = line.product_id
            target = line.target_id
            if not (product and target.partner_id):
                line.monthly_forecast = 0.0
                line.lead_time_days = 0
                line.safety_stock = 0.0
                line.available_qty = 0.0
                line.replenishment_qty = 0.0
                line.needs_replenishment = False
                continue

            company = target.company_id or self.env.company
            target_uom = line.uom_id or product.uom_id
            months = line._period_months()

            line.monthly_forecast = (line.target_qty / months) if months else 0.0

            seller = product._select_seller(
                partner_id=target.partner_id,
                quantity=line.target_qty or 1.0,
                uom_id=target_uom,
            )
            line.lead_time_days = seller.delay if seller else 0

            orderpoints = self.env['stock.warehouse.orderpoint'].search([
                ('product_id', '=', product.id),
                ('company_id', '=', company.id),
            ])
            line.safety_stock = line._convert_qty(
                sum(orderpoints.mapped('product_min_qty')),
                product.uom_id, target_uom)

            line.available_qty = line._convert_qty(
                product.with_company(company).free_qty,
                product.uom_id, target_uom)

            line.replenishment_qty = (
                line.monthly_forecast * (line.lead_time_days / 30.0)
                + line.safety_stock
                - line.available_qty
                - line.qty_ordered_not_received
            )
            line.needs_replenishment = (
                line.replenishment_qty > line._alert_tolerance())

    def _search_needs_replenishment(self, operator, value):
        """Make the computed flag filterable.

        The figure depends on live stock and open orders, so there is nothing
        stored to index: the only way to answer is to evaluate the active lines
        and return their ids. Restricted to active targets to keep that bounded.
        """
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise UserError(_(
                'Replenishment Needed can only be filtered as true or false.'))

        candidates = self.search([('target_id.state', '=', 'active')])
        breaching = candidates.filtered('needs_replenishment')
        wants_breaching = (operator == '=') == value
        if wants_breaching:
            return [('id', 'in', breaching.ids)]
        return [('id', 'not in', breaching.ids)]

    def _should_alert(self):
        """Whether this line is worth reporting right now.

        Reports a line that has newly breached, or whose shortfall has grown by
        more than the tolerance since it was last reported. Reusing the same
        tolerance for both means one setting controls how noisy the alerts are.
        """
        self.ensure_one()
        if not self.needs_replenishment:
            return False
        if not self.last_alert_date:
            return True
        return (self.replenishment_qty - self.last_alert_qty
                > self._alert_tolerance())

    def _alert_tolerance(self):
        """Shortfall below which a line is not worth reporting.

        Expressed as a share of the monthly forecast, so the same setting suits
        a product bought in tens and one bought in thousands.
        """
        self.ensure_one()
        company = self.target_id.company_id or self.env.company
        pct = company.purchase_target_alert_tolerance or 0.0
        return self.monthly_forecast * (pct / 100.0)

    @api.depends('product_id', 'uom_id', 'target_id.company_id')
    def _compute_current_stock_qty(self):
        for line in self:
            product = line.product_id
            if not product:
                line.current_stock_qty = 0.0
                continue
            company = line.target_id.company_id or self.env.company
            on_hand = product.with_company(company).qty_available
            line.current_stock_qty = line._convert_qty(
                on_hand, product.uom_id, line.uom_id or product.uom_id)

    @api.depends('product_id', 'uom_id', 'target_id.partner_id',
                 'target_id.company_id')
    def _compute_qty_ordered_not_received(self):
        """Outstanding quantity on this vendor's confirmed purchase orders.

        Read per order line rather than from a single aggregate, because
        product_qty and qty_received are both expressed in the order line's own
        unit and have to be netted before conversion. Over-receipts are floored
        at zero so a line delivered in excess cannot offset a genuine shortfall
        on another.
        """
        for line in self:
            target = line.target_id
            if not (line.product_id and target.partner_id):
                line.qty_ordered_not_received = 0.0
                continue

            target_uom = line.uom_id or line.product_id.uom_id
            order_lines = self.env['purchase.order.line'].search([
                ('product_id', '=', line.product_id.id),
                ('order_id.state', 'in', ['purchase', 'done']),
                ('order_id.partner_id', '=', target.partner_id.id),
                ('order_id.company_id', '=', target.company_id.id),
            ])
            pending = 0.0
            for pol in order_lines:
                outstanding = max(pol.product_qty - pol.qty_received, 0.0)
                if outstanding:
                    pending += line._convert_qty(
                        outstanding, pol.product_uom_id, target_uom)
            line.qty_ordered_not_received = pending

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    @api.depends('product_id', 'target_id.partner_id', 'uom_id', 'target_qty')
    def _compute_price_unit(self):
        """Default to this vendor's price for the product, else product cost."""
        for line in self:
            product = line.product_id
            if not product:
                line.price_unit = 0.0
                continue
            seller = product._select_seller(
                partner_id=line.target_id.partner_id,
                quantity=line.target_qty or 1.0,
                uom_id=line.uom_id or product.uom_id,
            )
            line.price_unit = seller.price if seller else product.standard_price

    @api.depends('target_qty', 'price_unit')
    def _compute_amount_untaxed(self):
        for line in self:
            line.amount_untaxed = line.target_qty * line.price_unit

    @api.depends('product_id', 'target_qty',
                 'uom_id', 'target_id.date_start', 'target_id.date_end',
                 'target_id.partner_id', 'target_id.company_id',
                 'target_id.currency_id')
    def _compute_achieved(self):
        for line in self:
            target = line.target_id
            if not (line.product_id and target.partner_id
                    and target.date_start and target.date_end):
                line.achieved_amount = 0.0
                line.achieved_qty = 0.0
                line.achieved_percentage = 0.0
                line.remaining_qty = 0.0
                continue

            line.achieved_amount, line.achieved_qty = \
                line._get_received_achievement()

            line.achieved_percentage = (
                (line.achieved_qty / line.target_qty) * 100.0
                if line.target_qty else 0.0
            )
            line.remaining_qty = max(
                line.target_qty - line.achieved_qty, 0.0)

    # ─────────────────── Achievement engine ───────────────────

    def _get_move_domain(self):
        """Done stock moves for this product, received against a confirmed PO
        from the target's vendor, within the target period.

        The move's own date is used, so goods are credited to the period they
        physically arrived in rather than the period the PO was raised in.
        """
        self.ensure_one()
        target = self.target_id
        return [
            ('state', '=', 'done'),
            ('product_id', '=', self.product_id.id),
            ('company_id', '=', target.company_id.id),
            ('purchase_line_id', '!=', False),
            ('purchase_line_id.order_id.state', 'in', ['purchase', 'done']),
            ('purchase_line_id.order_id.partner_id', '=', target.partner_id.id),
            ('date', '>=', datetime.combine(target.date_start, time.min)),
            ('date', '<=', datetime.combine(target.date_end, time.max)),
        ]

    @staticmethod
    def _get_move_sign(move):
        """+1 for goods arriving, -1 for goods returned to the vendor.

        Anything that neither enters nor leaves internal stock (an internal
        transfer, say) contributes nothing.
        """
        incoming = move.location_dest_id.usage == 'internal'
        outgoing = move.location_id.usage == 'internal'
        if incoming and not outgoing:
            return 1.0
        if outgoing and not incoming:
            return -1.0
        return 0.0

    def _convert_qty(self, qty, from_uom, to_uom):
        """Convert between units, leaving the value alone when the units are
        not convertible.

        Odoo 19 dropped uom category_id in favour of a unit hierarchy, so the
        ORM is asked to judge convertibility rather than comparing categories
        by hand -- raise_if_failure=False returns the original quantity when
        the two units are unrelated.
        """
        if not from_uom or not to_uom or from_uom == to_uom:
            return qty
        return from_uom._compute_quantity(qty, to_uom, raise_if_failure=False)

    def _get_received_achievement(self):
        """Return (amount, qty) actually received in the target period.

        Quantity is expressed in the line's unit of measure. Amount is the
        received quantity valued at the purchase order line's net unit price,
        converted into the target's currency.
        """
        self.ensure_one()
        target = self.target_id
        line_uom = self.uom_id or self.product_id.uom_id
        product_uom = self.product_id.uom_id

        amount = qty = 0.0
        moves = self.env['stock.move'].search(self._get_move_domain())
        for move in moves:
            sign = self._get_move_sign(move)
            if not sign:
                continue

            # ── Quantity, in the line's unit of measure ──
            qty += sign * self._convert_qty(
                move.quantity, move.product_uom, line_uom)

            # ── Value, priced from the originating purchase order line ──
            pol = move.purchase_line_id
            if not pol.product_uom_qty:
                continue
            # price_subtotal is net of the line discount and excludes tax,
            # matching the untaxed target amount;
            # product_uom_qty is the ordered quantity in the product's own unit,
            # so this gives a unit value directly comparable with the converted
            # move quantity.
            unit_value = pol.price_subtotal / pol.product_uom_qty
            move_qty = self._convert_qty(
                move.quantity, move.product_uom, product_uom)
            move_value = unit_value * move_qty

            order = pol.order_id
            if order.currency_id and order.currency_id != target.currency_id:
                move_value = order.currency_id._convert(
                    move_value,
                    target.currency_id,
                    order.company_id or target.company_id,
                    move.date.date(),
                )
            amount += sign * move_value

        return amount, qty

    # ─────────────────── Drill-down ───────────────────

    def _get_source_moves(self):
        """Done stock moves this line's achievement was measured from."""
        self.ensure_one()
        if not (self.product_id and self.target_id.partner_id
                and self.target_id.date_start and self.target_id.date_end):
            return self.env['stock.move']
        return self.env['stock.move'].search(self._get_move_domain())

    def action_view_purchase_orders(self):
        """Open the purchase orders behind the receipts counted for this line.

        Built from the same move domain the achievement uses, so the orders
        listed are exactly those that contributed to the figures.
        """
        self.ensure_one()
        orders = self._get_source_moves().purchase_line_id.order_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders - %s', self.product_id.display_name),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', orders.ids)],
            'context': {'create': False},
        }

    def action_view_receipts(self):
        """Open the receipts that actually delivered the counted quantity.

        Achievement here is measured on goods received rather than ordered, so
        the receipts are the closer evidence when a figure is queried.
        """
        self.ensure_one()
        pickings = self._get_source_moves().picking_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Receipts - %s', self.product_id.display_name),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pickings.ids)],
            'context': {'create': False},
        }
