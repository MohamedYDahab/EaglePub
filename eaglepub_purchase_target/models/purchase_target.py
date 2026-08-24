from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PurchaseTarget(models.Model):
    _name = 'purchase.target'
    # activity.mixin as well as thread: the digest logs a to-do, and
    # activity_schedule lives on the activity mixin.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Purchase Target'
    _order = 'date_start desc'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        tracking=True,
        # Deliberately unrestricted: a supplier_rank filter hides any partner
        # not yet used on a purchase, so brand new vendors could not be
        # targeted at all.
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
        help='Who receives the replenishment alerts for this target.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    period_type = fields.Selection(
        [
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
            ('custom', 'Custom'),
        ],
        string='Period Type',
        required=True,
        default='monthly',
    )
    date_start = fields.Date(string='Start Date', required=True, tracking=True)
    date_end = fields.Date(string='End Date', required=True, tracking=True)
    auto_renew = fields.Boolean(
        string='Auto-Renew',
        default=False,
        help='Automatically create the next period target when this one expires.',
    )
    state = fields.Selection(
        [
            ('active', 'Active'),
            ('expired', 'Expired'),
        ],
        string='Status',
        default='active',
        compute='_compute_state',
        store=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        'purchase.target.line',
        'target_id',
        string='Target Lines',
    )

    # ── Rolled-up totals ──
    total_amount_untaxed = fields.Monetary(
        string='Target Value',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='What these targets are worth if fully achieved, excluding tax.',
    )
    total_achieved = fields.Monetary(
        string='Received Value',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Value actually received, excluding tax. Informational: progress '
             'is measured on quantity.',
    )
    total_target_qty = fields.Float(
        string='Target (Qty)',
        compute='_compute_totals',
        store=True,
        digits='Product Unit of Measure',
    )
    total_achieved_qty = fields.Float(
        string='Received (Qty)',
        compute='_compute_totals',
        store=True,
        digits='Product Unit of Measure',
    )
    remaining_qty_total = fields.Float(
        string='Remaining (Qty)',
        compute='_compute_totals',
        store=True,
        digits='Product Unit of Measure',
    )
    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_totals',
        store=True,
        help='Received quantity over target quantity. Targets are set in '
             'quantity, so value is reported but never drives progress.',
    )

    @api.depends('partner_id', 'date_start', 'date_end')
    def _compute_name(self):
        for rec in self:
            period = ''
            if rec.date_start and rec.date_end:
                period = f" ({rec.date_start} - {rec.date_end})"
            rec.name = (rec.partner_id.name or 'New') + period

    @api.depends('date_end')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date_end and rec.date_end < today:
                rec.state = 'expired'
            else:
                rec.state = 'active'

    @api.depends('line_ids.target_qty', 'line_ids.achieved_qty',
                 'line_ids.amount_untaxed', 'line_ids.achieved_amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_target_qty = sum(rec.line_ids.mapped('target_qty'))
            rec.total_achieved_qty = sum(rec.line_ids.mapped('achieved_qty'))
            rec.remaining_qty_total = (rec.total_target_qty
                                       - rec.total_achieved_qty)
            rec.total_amount_untaxed = sum(rec.line_ids.mapped('amount_untaxed'))
            rec.total_achieved = sum(rec.line_ids.mapped('achieved_amount'))
            # Targets are set in quantity, so quantity alone drives progress.
            rec.progress = (
                (rec.total_achieved_qty / rec.total_target_qty) * 100.0
                if rec.total_target_qty else 0.0
            )

    @api.onchange('period_type')
    def _onchange_period_type(self):
        today = fields.Date.context_today(self)
        if self.period_type == 'monthly':
            self.date_start = today.replace(day=1)
            self.date_end = today.replace(day=1) + relativedelta(months=1, days=-1)
        elif self.period_type == 'quarterly':
            quarter = (today.month - 1) // 3
            self.date_start = today.replace(month=quarter * 3 + 1, day=1)
            self.date_end = (today.replace(month=quarter * 3 + 1, day=1)
                             + relativedelta(months=3, days=-1))
        elif self.period_type == 'yearly':
            self.date_start = today.replace(month=1, day=1)
            self.date_end = today.replace(month=12, day=31)

    # ─────────────────── Actions ───────────────────

    def action_refresh(self):
        """Recompute achievement from the source documents.

        The totals are stored so the list, graph and pivot views can aggregate
        them in SQL. Storing makes them a snapshot: nothing recomputes when a
        receipt is validated elsewhere, so this button and the nightly cron are
        what keep them current.
        """
        self.line_ids.invalidate_recordset()
        self.invalidate_recordset()
        self.line_ids._compute_achieved()
        self._compute_totals()
        self.env.flush_all()
        return True

    @api.model
    def _cron_refresh_targets(self):
        """Keep the stored achievement figures current."""
        self.search([('state', '=', 'active')]).action_refresh()

    def _get_next_period_dates(self):
        """Start and end dates for the period following this one."""
        self.ensure_one()
        if not (self.date_start and self.date_end):
            raise UserError(_(
                'Set a start and end date before creating the next period.'))
        if self.period_type == 'monthly':
            new_start = self.date_start + relativedelta(months=1)
            new_end = new_start + relativedelta(months=1, days=-1)
        elif self.period_type == 'quarterly':
            new_start = self.date_start + relativedelta(months=3)
            new_end = new_start + relativedelta(months=3, days=-1)
        elif self.period_type == 'yearly':
            new_start = self.date_start + relativedelta(years=1)
            new_end = new_start + relativedelta(years=1, days=-1)
        else:
            new_start = self.date_end + relativedelta(days=1)
            duration = (self.date_end - self.date_start).days
            new_end = new_start + relativedelta(days=duration)
        return new_start, new_end

    def _create_next_period(self):
        self.ensure_one()
        new_start, new_end = self._get_next_period_dates()
        return self.copy({
            'date_start': new_start,
            'date_end': new_end,
        })

    def action_next_period(self):
        self.ensure_one()
        new_target = self._create_next_period()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.target',
            'res_id': new_target.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ─────────────────── Replenishment alerts ───────────────────

    @api.model
    def _cron_notify_replenishment(self):
        """Report target lines that will run short before a new order arrives.

        One digest per target rather than per line: a target is already scoped
        to a single vendor and carries a responsible user, so it is the natural
        place to post. A line is reported when it newly breaches, or when its
        shortfall has grown by more than the tolerance since it was last
        reported -- otherwise the same lines would arrive every morning and be
        filtered away within a week.
        """
        for target in self.search([('state', '=', 'active')]):
            due = target.line_ids.filtered(lambda l: l._should_alert())
            if not due:
                continue
            target._post_replenishment_digest(due)
            now = fields.Datetime.now()
            for line in due:
                line.last_alert_qty = line.replenishment_qty
                line.last_alert_date = now

        # A line that has recovered forgets its history, so it can report again
        # cleanly next time it slips.
        recovered = self.env['purchase.target.line'].search(
            [('last_alert_date', '!=', False)])
        recovered.filtered(lambda l: not l.needs_replenishment).write({
            'last_alert_qty': 0.0, 'last_alert_date': False,
        })

    def _replenishment_recipients(self):
        """Everyone told about a shortfall on this target.

        The responsible owns the to-do; followers asked to see this record; and
        the purchase managers are the safety net, because a target with no
        responsible would otherwise notify nobody at all while the cron
        reported success.

        Recipients are listed explicitly rather than left to the message
        subtype: relying on follower subscription alone proved not to reach
        followers reliably, and a missed replenishment warning is not something
        to leave to a default.
        """
        self.ensure_one()
        partners = self.user_id.partner_id | self.message_partner_ids
        managers = self.env.ref('purchase.group_purchase_manager',
                                raise_if_not_found=False)
        if managers:
            # all_user_ids rather than user_ids: it includes managers who hold
            # the group through inheritance rather than directly.
            partners |= managers.all_user_ids.partner_id
        return partners

    def _post_replenishment_digest(self, lines):
        """Post one message listing the lines needing action, and log a to-do.

        The body is built with Markup because message_post escapes a plain
        string: passing raw HTML renders the tags as visible text. Markup's %
        operator also escapes the substituted values, so a product name
        containing an ampersand cannot break the table.
        """
        self.ensure_one()
        row = Markup(
            '<tr><td>%s</td>'
            '<td style="text-align:right;">%.2f</td>'
            '<td style="text-align:right;">%.2f</td>'
            '<td style="text-align:right;">%s</td>'
            '<td style="text-align:right;">%.2f</td>'
            '<td style="text-align:right;">%.2f</td>'
            '<td style="text-align:right;"><b>%.2f</b></td></tr>'
        )
        rows = Markup('').join(
            row % (
                line.product_id.display_name,
                line.monthly_forecast,
                line.safety_stock,
                line.lead_time_days,
                line.available_qty,
                line.qty_ordered_not_received,
                line.replenishment_qty,
            ) for line in lines)

        body = Markup(
            '<p>%s product(s) on <b>%s</b> will run short before a new order '
            'could arrive.</p>'
            '<table class="table table-sm">'
            '<thead><tr>'
            '<th>Product</th>'
            '<th style="text-align:right;">Monthly forecast</th>'
            '<th style="text-align:right;">Safety stock</th>'
            '<th style="text-align:right;">Lead days</th>'
            '<th style="text-align:right;">Available</th>'
            '<th style="text-align:right;">On order</th>'
            '<th style="text-align:right;">To replenish</th>'
            '</tr></thead><tbody>%s</tbody></table>'
        ) % (len(lines), self.display_name, rows)

        # message_notify rather than message_post: message_post silently
        # narrowed the recipient list to the responsible alone, dropping the
        # followers and the manager safety net. message_notify delivers to
        # exactly the partners it is given, which is what a warning needs.
        self.message_notify(
            body=body,
            subject=_('Replenishment needed - %s', self.partner_id.display_name),
            partner_ids=self._replenishment_recipients().ids,
        )
        if self.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.user_id.id,
                summary=_('Replenish %s product(s) from %s',
                          len(lines), self.partner_id.display_name),
            )

    @api.model
    def _cron_update_expired_targets(self):
        """Flag targets whose period has ended, renewing them when asked to."""
        today = fields.Date.context_today(self)
        targets = self.search([
            ('state', '=', 'active'),
            ('date_end', '<', today),
        ])
        for target in targets:
            target.state = 'expired'
            if target.auto_renew:
                target._create_next_period()
