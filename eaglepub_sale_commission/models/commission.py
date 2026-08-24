from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EaglepubCommission(models.Model):
    _name = 'eaglepub.commission'
    _description = 'Commission'
    _inherit = ['mail.thread']
    _order = 'date_to desc, user_id, id'
    _rec_name = 'display_name'

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Salesperson',
        required=True,
        index=True,
        tracking=True,
    )
    plan_id = fields.Many2one(
        comodel_name='eaglepub.commission.plan',
        string='Plan',
        required=True,
        tracking=True,
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True,
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('paid', 'Paid'),
            ('cancel', 'Cancelled'),
        ],
        default='draft',
        required=True,
        tracking=True,
    )

    line_ids = fields.One2many(
        comodel_name='eaglepub.commission.line',
        inverse_name='commission_id',
        string='Detail',
    )
    base_amount = fields.Monetary(
        compute='_compute_amounts', store=True,
        help='Total of what the commission was calculated on.',
    )
    commission_amount = fields.Monetary(
        compute='_compute_amounts', store=True, tracking=True,
    )
    line_count = fields.Integer(compute='_compute_amounts', store=True)

    display_name = fields.Char(compute='_compute_display_name', store=True)

    _period_positive = models.Constraint(
        'CHECK(date_from <= date_to)',
        'The start date must come before the end date.',
    )

    @api.depends('line_ids.base_amount', 'line_ids.amount')
    def _compute_amounts(self):
        for rec in self:
            rec.base_amount = sum(rec.line_ids.mapped('base_amount'))
            rec.commission_amount = sum(rec.line_ids.mapped('amount'))
            rec.line_count = len(rec.line_ids)

    @api.depends('user_id', 'date_from', 'date_to')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s to %s' % (
                rec.user_id.name or '', rec.date_from or '', rec.date_to or '')

    # ─────────────────── Actions ───────────────────

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_(
                    'There is nothing to confirm: this commission has no lines.'
                ))
        self.write({'state': 'confirmed'})

    def action_mark_paid(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(_(
                    'Only a confirmed commission can be marked as paid.'
                ))
        self.write({'state': 'paid'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Commission Detail'),
            'res_model': 'eaglepub.commission.line',
            'view_mode': 'list,form',
            'domain': [('commission_id', '=', self.id)],
            'context': {'default_commission_id': self.id},
        }


class EaglepubCommissionLine(models.Model):
    _name = 'eaglepub.commission.line'
    _description = 'Commission Detail Line'
    _order = 'date, id'

    commission_id = fields.Many2one(
        comodel_name='eaglepub.commission',
        # Explicit label: the default would be "Commission", clashing with the
        # amount field below and making the two indistinguishable in exports.
        string='Commission Record',
        required=True,
        ondelete='cascade',
        index=True,
    )
    currency_id = fields.Many2one(
        related='commission_id.currency_id',
        readonly=True,
    )

    date = fields.Date()
    reference = fields.Char(help='The document this line came from.')
    partner_id = fields.Many2one('res.partner', string='Customer')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float()

    move_id = fields.Many2one('account.move', string='Invoice')
    order_id = fields.Many2one('sale.order', string='Sales Order')

    base_amount = fields.Monetary(
        help='Revenue or margin this line contributed, before the rate.',
    )
    rate = fields.Float(string='Rate (%)')
    amount = fields.Monetary(string='Commission')
