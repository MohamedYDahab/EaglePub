from odoo import models, fields, api
from dateutil.relativedelta import relativedelta


class SaleTarget(models.Model):
    _name = 'sale.target'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Sales Target'
    _order = 'date_start desc'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
    )
    target_scope = fields.Selection(
        [
            ('sales', 'Sales Target'),
            ('material', 'Material Movement'),
        ],
        string='Scope',
        required=True,
        default='sales',
        help='Which set of targets this record belongs to. The two sets share '
             'the same fields and the same achievement logic, but each menu '
             'shows only its own records.',
    )
    assign_to = fields.Selection(
        [
            ('salesperson', 'Salesperson'),
            ('team', 'Sales Team'),
        ],
        string='Assign To',
        required=True,
        default='salesperson',
        tracking=True,
    )
    salesperson_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        domain=[('share', '=', False)],
        tracking=True,
    )
    team_id = fields.Many2one(
        'crm.team',
        string='Sales Team',
        tracking=True,
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
        default=lambda self: self.env.company.currency_id.id,
        required=True,
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
    date_start = fields.Date(string='Start Date', tracking=True)
    date_end = fields.Date(string='End Date', tracking=True)
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
        'sale.target.line',
        'target_id',
        string='Target Lines',
    )
    total_amount_untaxed = fields.Monetary(
        string='Target Value',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='What these targets are worth if fully achieved, excluding tax.',
    )
    total_achieved = fields.Monetary(
        string='Achieved Value',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        help='Value actually sold, excluding tax. Informational: progress is '
             'measured on quantity.',
    )
    total_target_qty = fields.Float(
        string='Target (Qty)',
        compute='_compute_totals',
        store=True,
        digits='Product Unit of Measure',
    )
    total_achieved_qty = fields.Float(
        string='Achieved (Qty)',
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
        help='Achieved quantity over target quantity. Targets are set in '
             'quantity, so value is reported but never drives progress.',
    )

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        """Subscribe the salesperson, or the leader of the target's team.

        Odoo's default only recognises a field literally named user_id, and this
        model uses salesperson_id. That matters more than it sounds: a tracking
        message is only written when somebody is following, so without this the
        chatter would stay empty no matter what changed on the record.
        """
        res = super()._message_auto_subscribe_followers(
            updated_values, default_subtype_ids)

        users = self.env['res.users']
        if updated_values.get('salesperson_id'):
            users |= users.sudo().browse(updated_values['salesperson_id'])
        if updated_values.get('team_id'):
            team = self.env['crm.team'].sudo().browse(updated_values['team_id'])
            users |= team.user_id

        for user in users:
            if not (user.active and user.partner_id):
                continue
            # No assignment template: mail.message_user_assigned renders
            # object.user_id, which this model does not have. Subscribing
            # silently is what matters -- it is what makes tracking work.
            res.append((user.partner_id.id, default_subtype_ids, False))
        return res

    @api.depends('salesperson_id', 'team_id', 'assign_to', 'date_start', 'date_end')
    def _compute_name(self):
        for rec in self:
            assignee = ''
            if rec.assign_to == 'salesperson' and rec.salesperson_id:
                assignee = rec.salesperson_id.name
            elif rec.assign_to == 'team' and rec.team_id:
                assignee = rec.team_id.name
            period = ''
            if rec.date_start and rec.date_end:
                period = f" ({rec.date_start} - {rec.date_end})"
            rec.name = (assignee or 'New') + period

    @api.depends('date_end')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for target in self:
            if target.date_end and target.date_end < today:
                target.state = 'expired'
            else:
                target.state = 'active'

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

    @api.model
    def _cron_update_expired_targets(self):
        """Cron job to update expired targets and auto-renew if enabled."""
        today = fields.Date.context_today(self)
        targets = self.search([
            ('state', '=', 'active'),
            ('date_end', '<', today),
        ])
        for target in targets:
            target.state = 'expired'
            if target.auto_renew:
                target._create_next_period()

    @api.onchange('period_type')
    def _onchange_period_type(self):
        today = fields.Date.context_today(self)
        if self.period_type == 'monthly':
            self.date_start = today.replace(day=1)
            self.date_end = today.replace(day=1) + relativedelta(months=1, days=-1)
        elif self.period_type == 'quarterly':
            quarter = (today.month - 1) // 3
            self.date_start = today.replace(month=quarter * 3 + 1, day=1)
            self.date_end = today.replace(month=quarter * 3 + 1, day=1) + relativedelta(months=3, days=-1)
        elif self.period_type == 'yearly':
            self.date_start = today.replace(month=1, day=1)
            self.date_end = today.replace(month=12, day=31)
        elif self.period_type == 'custom':
            self.date_start = False
            self.date_end = False

    @api.onchange('assign_to')
    def _onchange_assign_to(self):
        if self.assign_to == 'salesperson':
            self.team_id = False
        elif self.assign_to == 'team':
            self.salesperson_id = False

    def action_refresh(self):
        """Recompute achievement from the source documents.

        The totals are stored so the list, graph and pivot views can aggregate
        them in SQL. Storing makes them a snapshot: nothing recomputes when an
        order is confirmed elsewhere, so this button and the nightly cron are
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
        """Calculate start and end dates for the next period."""
        self.ensure_one()
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
        """Create a duplicate target for the next period."""
        self.ensure_one()
        new_start, new_end = self._get_next_period_dates()
        return self.copy({
            'date_start': new_start,
            'date_end': new_end,
        })

    def action_next_period(self):
        """Manually duplicate this target for the next period."""
        self.ensure_one()
        new_target = self._create_next_period()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.target',
            'res_id': new_target.id,
            'view_mode': 'form',
            'target': 'current',
        }
