# -*- coding: utf-8 -*-
import calendar
from datetime import date, datetime, time

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


MONTH_SELECTION = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'),
    ('4', 'April'), ('5', 'May'), ('6', 'June'),
    ('7', 'July'), ('8', 'August'), ('9', 'September'),
    ('10', 'October'), ('11', 'November'), ('12', 'December'),
]


class SalesTarget(models.Model):
    _name = 'sales.target'
    _inherit = ['mail.thread']
    _description = 'Sales Target'
    _order = 'year desc, month desc'
    _rec_name = 'display_name'

    # ── Target Type ──
    target_type = fields.Selection([
        ('salesperson', 'Salesperson'),
        ('pos', 'Point of Sale'),
    ], string='Target Type', required=True, default='salesperson',
        tracking=True,
    )

    # ── Salesperson mode fields ──
    user_id = fields.Many2one(
        'res.users', string='Salesperson',
        domain=[('share', '=', False)],
        tracking=True,
    )

    # ── POS mode fields ──
    pos_config_id = fields.Many2one(
        'pos.config', string='Point of Sale',
        tracking=True,
    )

    # ── Common fields ──
    month = fields.Selection(
        MONTH_SELECTION, string='Month', required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    year = fields.Integer(
        string='Year', required=True,
        default=lambda self: fields.Date.today().year,
    )
    target_amount = fields.Monetary(
        string='Target Amount', required=True,
        currency_field='currency_id',
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Currency',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)

    # ── Computed Achievement Fields ──
    invoice_amount = fields.Monetary(
        string='Invoice Amount', currency_field='currency_id',
        compute='_compute_achieved', store=True, readonly=True,
    )
    pos_amount = fields.Monetary(
        string='POS Amount', currency_field='currency_id',
        compute='_compute_achieved', store=True, readonly=True,
    )
    achieved_amount = fields.Monetary(
        string='Achieved Amount', currency_field='currency_id',
        compute='_compute_achieved', store=True, readonly=True,
    )
    achievement_ratio = fields.Float(
        string='Achievement %',
        compute='_compute_achieved', store=True, readonly=True,
    )
    remaining_amount = fields.Monetary(
        string='Remaining', currency_field='currency_id',
        compute='_compute_achieved', store=True, readonly=True,
    )

    # ── Detail Lines ──
    line_ids = fields.One2many(
        'sales.target.line', 'target_id', string='Detail Lines',
    )

    # ── Display ──
    display_name = fields.Char(
        compute='_compute_display_name', store=True,
    )

    # ── Constraints ──
    _positive_target = models.Constraint(
        'CHECK(target_amount >= 0)',
        'Target amount must be positive!',
    )

    @api.constrains('target_type', 'user_id', 'pos_config_id')
    def _check_target_owner(self):
        for rec in self:
            if rec.target_type == 'salesperson' and not rec.user_id:
                raise ValidationError(
                    _('Salesperson is required for salesperson targets.'))
            if rec.target_type == 'pos' and not rec.pos_config_id:
                raise ValidationError(
                    _('Point of Sale is required for POS targets.'))

    @api.constrains('target_type', 'user_id', 'pos_config_id',
                     'month', 'year', 'company_id')
    def _check_unique_target(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('target_type', '=', rec.target_type),
                ('month', '=', rec.month),
                ('year', '=', rec.year),
                ('company_id', '=', rec.company_id.id),
            ]
            if rec.target_type == 'salesperson':
                domain.append(('user_id', '=', rec.user_id.id))
            else:
                domain.append(('pos_config_id', '=', rec.pos_config_id.id))
            if self.search_count(domain):
                raise ValidationError(_(
                    'A target already exists for this '
                    'month/year combination!'))

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year < 2020 or rec.year > 2099:
                raise ValidationError(
                    _('Year must be between 2020 and 2099.'))

    @api.depends('target_type', 'user_id', 'pos_config_id',
                 'month', 'year')
    def _compute_display_name(self):
        month_dict = dict(MONTH_SELECTION)
        for rec in self:
            month_name = month_dict.get(rec.month, '')
            if rec.target_type == 'salesperson':
                name = rec.user_id.name or ''
            else:
                name = rec.pos_config_id.name or ''
            rec.display_name = f"{name} - {month_name} {rec.year}"

    @api.onchange('target_type')
    def _onchange_target_type(self):
        """Clear irrelevant field when switching type."""
        if self.target_type == 'salesperson':
            self.pos_config_id = False
        else:
            self.user_id = False

    # ─────────────────── Achievement Computation ───────────────────

    def _get_date_range(self):
        """Return (date_from, date_to) for the target's month/year."""
        self.ensure_one()
        m = int(self.month)
        y = self.year
        last_day = calendar.monthrange(y, m)[1]
        return date(y, m, 1), date(y, m, last_day)

    @api.depends('target_type', 'user_id', 'pos_config_id',
                 'month', 'year', 'target_amount',
                 'company_id', 'state')
    def _compute_achieved(self):
        for rec in self:
            date_from, date_to = rec._get_date_range()

            if rec.target_type == 'salesperson' and rec.user_id:
                inv_amt = rec._compute_invoice_amount(date_from, date_to)
                rec.invoice_amount = inv_amt
                rec.pos_amount = 0
                rec.achieved_amount = inv_amt
            elif rec.target_type == 'pos' and rec.pos_config_id:
                pos_amt = rec._compute_pos_amount(date_from, date_to)
                rec.invoice_amount = 0
                rec.pos_amount = pos_amt
                rec.achieved_amount = pos_amt
            else:
                rec.invoice_amount = 0
                rec.pos_amount = 0
                rec.achieved_amount = 0

            rec.achievement_ratio = (
                (rec.achieved_amount / rec.target_amount * 100)
                if rec.target_amount else 0
            )
            rec.remaining_amount = rec.target_amount - rec.achieved_amount

    def _compute_invoice_amount(self, date_from, date_to):
        """Net invoiced amount = invoices - credit notes (posted only)
        for the salesperson."""
        self.ensure_one()
        moves = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('invoice_user_id', '=', self.user_id.id),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('company_id', '=', self.company_id.id),
        ])
        return sum(moves.mapped('amount_untaxed_signed'))

    def _compute_pos_amount(self, date_from, date_to):
        """Total POS order amount for the selected POS config."""
        self.ensure_one()
        dt_from = datetime.combine(date_from, time.min)
        dt_to = datetime.combine(date_to, time.max)

        pos_orders = self.env['pos.order'].search([
            ('state', 'in', ['paid', 'done']),
            ('config_id', '=', self.pos_config_id.id),
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('company_id', '=', self.company_id.id),
        ])
        return sum(pos_orders.mapped('amount_total')) - \
            sum(pos_orders.mapped('amount_tax'))

    # ─────────────────── Actions ───────────────────

    def action_confirm(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'confirmed'

    def action_close(self):
        for rec in self:
            if rec.state == 'confirmed':
                rec.state = 'closed'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_refresh(self):
        """Recompute achievements and regenerate detail lines."""
        self._compute_achieved()
        self._generate_detail_lines()
        return True

    def _generate_detail_lines(self):
        """Populate detail lines from invoices or POS orders."""
        for rec in self:
            rec.line_ids.unlink()
            date_from, date_to = rec._get_date_range()
            lines_vals = []

            if rec.target_type == 'salesperson' and rec.user_id:
                # ── Invoice / Credit Note lines ──
                invoices = self.env['account.move'].search([
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('state', '=', 'posted'),
                    ('invoice_user_id', '=', rec.user_id.id),
                    ('invoice_date', '>=', date_from),
                    ('invoice_date', '<=', date_to),
                    ('company_id', '=', rec.company_id.id),
                ])
                for inv in invoices:
                    source = ('invoice'
                              if inv.move_type == 'out_invoice'
                              else 'credit_note')
                    lines_vals.append({
                        'target_id': rec.id,
                        'source_type': source,
                        'reference': inv.name,
                        'partner_id': inv.partner_id.id,
                        'date': inv.invoice_date,
                        'amount': inv.amount_untaxed_signed,
                        'move_id': inv.id,
                    })

            elif rec.target_type == 'pos' and rec.pos_config_id:
                # ── POS order lines ──
                dt_from = datetime.combine(date_from, time.min)
                dt_to = datetime.combine(date_to, time.max)
                pos_orders = self.env['pos.order'].search([
                    ('state', 'in', ['paid', 'done']),
                    ('config_id', '=', rec.pos_config_id.id),
                    ('date_order', '>=', dt_from),
                    ('date_order', '<=', dt_to),
                    ('company_id', '=', rec.company_id.id),
                ])
                for po in pos_orders:
                    lines_vals.append({
                        'target_id': rec.id,
                        'source_type': 'pos',
                        'reference': po.pos_reference or po.name,
                        'partner_id': (po.partner_id.id
                                       if po.partner_id else False),
                        'date': po.date_order.date(),
                        'amount': po.amount_total - po.amount_tax,
                        'pos_order_id': po.id,
                    })

            if lines_vals:
                self.env['sales.target.line'].create(lines_vals)


    # ─────────────────── Dashboard API ───────────────────

    @api.model
    def get_dashboard_data(self, month=None, year=None):
        """Return dashboard KPIs, ranking, and chart data."""
        today = fields.Date.today()
        month = month or str(today.month)
        year = year or today.year

        domain = [
            ('month', '=', month),
            ('year', '=', year),
            ('company_id', '=', self.env.company.id),
        ]
        targets = self.search(domain)

        total_target = sum(targets.mapped('target_amount'))
        total_achieved = sum(targets.mapped('achieved_amount'))
        total_invoice = sum(targets.mapped('invoice_amount'))
        total_pos = sum(targets.mapped('pos_amount'))
        overall_ratio = round(
            (total_achieved / total_target * 100)
            if total_target else 0, 1)
        on_target = len(
            targets.filtered(lambda t: t.achievement_ratio >= 100))

        # Ranking sorted by ratio desc
        ranking = []
        for t in targets.sorted(
                key=lambda r: r.achievement_ratio, reverse=True):
            name = (t.user_id.name if t.target_type == 'salesperson'
                    else t.pos_config_id.name)
            ranking.append({
                'id': t.id,
                'name': name or '',
                'target_type': t.target_type,
                'target': t.target_amount,
                'achieved': t.achieved_amount,
                'ratio': round(t.achievement_ratio, 1),
                'remaining': t.remaining_amount,
            })

        # Bar chart: top 15
        chart_data = [{
            'name': r['name'],
            'target': r['target'],
            'achieved': r['achieved'],
        } for r in ranking[:15]]

        # Monthly trend for the year
        month_names = dict(MONTH_SELECTION)
        trend = []
        for m_val in range(1, 13):
            m_str = str(m_val)
            m_targets = self.search([
                ('month', '=', m_str),
                ('year', '=', year),
                ('company_id', '=', self.env.company.id),
            ])
            trend.append({
                'month': month_names.get(m_str, m_str),
                'target': sum(m_targets.mapped('target_amount')),
                'achieved': sum(m_targets.mapped('achieved_amount')),
            })

        return {
            'total_target': total_target,
            'total_achieved': total_achieved,
            'total_invoice': total_invoice,
            'total_pos': total_pos,
            'overall_ratio': overall_ratio,
            'target_count': len(targets),
            'on_target_count': on_target,
            'below_target_count': len(targets) - on_target,
            'ranking': ranking,
            'chart_data': chart_data,
            'trend_data': trend,
            'currency_symbol': self.env.company.currency_id.symbol or '',
        }


class SalesTargetLine(models.Model):
    _name = 'sales.target.line'
    _description = 'Sales Target Detail Line'
    _order = 'date desc'

    target_id = fields.Many2one(
        'sales.target', string='Target', ondelete='cascade',
    )
    source_type = fields.Selection([
        ('invoice', 'Invoice'),
        ('credit_note', 'Credit Note'),
        ('pos', 'POS Order'),
    ], string='Source Type')
    reference = fields.Char(string='Reference')
    partner_id = fields.Many2one('res.partner', string='Customer')
    date = fields.Date(string='Date')
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='target_id.currency_id',
    )
    move_id = fields.Many2one('account.move', string='Invoice')
    pos_order_id = fields.Many2one('pos.order', string='POS Order')
