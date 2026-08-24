from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EaglepubCommissionComputeWizard(models.TransientModel):
    _name = 'eaglepub.commission.compute.wizard'
    _description = 'Compute Commissions'

    date_from = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    user_ids = fields.Many2many(
        comodel_name='res.users',
        string='Salespeople',
        help='Leave empty to cover everyone who has a commission plan.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        required=True,
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from > wiz.date_to:
                raise UserError(_('The start date must come before the end date.'))

    # ──────────────────────────────────────────────────────────────
    # Collection
    # ──────────────────────────────────────────────────────────────

    def _base_of(self, plan, product, subtotal, quantity):
        """What the rate is applied to, before the sign is taken into account.

        Margin is worked out against the product's cost rather than a
        purchase_price field, so this does not require sale_margin to be
        installed.
        """
        if plan.base_on == 'margin':
            cost = (product.standard_price or 0.0) * (quantity or 0.0)
            return subtotal - cost
        return subtotal

    def _collect_invoices(self, plan, user):
        domain = [
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('invoice_user_id', '=', user.id),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
        ]
        if plan.basis == 'payment_received':
            # in_payment counts: the customer has paid, the reconciliation is
            # simply still in transit.
            domain.append(('payment_state', 'in', ('paid', 'in_payment')))

        vals = []
        for move in self.env['account.move'].search(domain):
            # A credit note gives money back, so it takes commission back too.
            sign = -1 if move.move_type == 'out_refund' else 1
            for line in move.invoice_line_ids:
                # Careful: display_type means the opposite thing on the two
                # models. A real invoice line is display_type == 'product',
                # while a real order line has display_type False. Testing for
                # truthiness here would skip every product line on the invoice.
                if line.display_type != 'product' or not line.product_id:
                    continue
                rule = plan.rule_for_product(line.product_id)
                if not rule:
                    continue
                base = self._base_of(
                    plan, line.product_id, line.price_subtotal, line.quantity) * sign
                vals.append({
                    'date': move.invoice_date,
                    'reference': move.name,
                    'partner_id': move.partner_id.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity * sign,
                    'move_id': move.id,
                    'base_amount': base,
                    'rate': rule.rate,
                    'amount': base * rule.rate / 100.0,
                })
        return vals

    def _collect_sale_orders(self, plan, user):
        domain = [
            ('state', '=', 'sale'),
            ('user_id', '=', user.id),
            ('date_order', '>=', datetime.combine(self.date_from, time.min)),
            ('date_order', '<=', datetime.combine(self.date_to, time.max)),
            ('company_id', '=', self.company_id.id),
        ]
        vals = []
        for order in self.env['sale.order'].search(domain):
            for line in order.order_line:
                # Here truthiness IS right: on a sale order line display_type
                # is only set for sections, subsections and notes.
                if line.display_type or not line.product_id:
                    continue
                rule = plan.rule_for_product(line.product_id)
                if not rule:
                    continue
                base = self._base_of(
                    plan, line.product_id, line.price_subtotal, line.product_uom_qty)
                vals.append({
                    'date': order.date_order.date(),
                    'reference': order.name,
                    'partner_id': order.partner_id.id,
                    'product_id': line.product_id.id,
                    'quantity': line.product_uom_qty,
                    'order_id': order.id,
                    'base_amount': base,
                    'rate': rule.rate,
                    'amount': base * rule.rate / 100.0,
                })
        return vals

    def _collect_for(self, plan, user):
        """Every commissionable line for one salesperson under one plan.

        The single extension point for new sources: a bridge module overrides
        this, calls super() and appends its own lines, rather than reimplementing
        action_compute.
        """
        if plan.basis == 'so_confirm':
            return self._collect_sale_orders(plan, user)
        return self._collect_invoices(plan, user)

    # ──────────────────────────────────────────────────────────────
    # Generation
    # ──────────────────────────────────────────────────────────────

    def action_compute(self):
        self.ensure_one()

        users = self.user_ids or self.env['res.users'].search([
            ('eaglepub_commission_plan_id', '!=', False),
        ])
        users = users.filtered(lambda u: u.eaglepub_commission_plan_id)
        if not users:
            raise UserError(_(
                'Nobody in this selection has a commission plan. Assign one on '
                'the salesperson before computing.'
            ))

        Commission = self.env['eaglepub.commission']
        created = Commission
        for user in users:
            plan = user.eaglepub_commission_plan_id
            lines = self._collect_for(plan, user)
            if not lines:
                continue

            # Recomputing a period replaces its draft record rather than
            # stacking a second one on top.
            existing = Commission.search([
                ('user_id', '=', user.id),
                ('date_from', '=', self.date_from),
                ('date_to', '=', self.date_to),
                ('state', '=', 'draft'),
                ('company_id', '=', self.company_id.id),
            ])
            existing.unlink()

            created |= Commission.create({
                'user_id': user.id,
                'plan_id': plan.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'company_id': self.company_id.id,
                'line_ids': [(0, 0, v) for v in lines],
            })

        if not created:
            raise UserError(_(
                'Nothing was found to commission in this period.'
            ))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Commissions'),
            'res_model': 'eaglepub.commission',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
        }
