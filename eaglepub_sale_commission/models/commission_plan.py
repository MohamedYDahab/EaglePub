from odoo import api, fields, models


class EaglepubCommissionPlan(models.Model):
    _name = 'eaglepub.commission.plan'
    _description = 'Commission Plan'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        required=True,
    )

    basis = fields.Selection(
        selection=[
            ('so_confirm', 'Confirmed Sales Order'),
            ('invoice_posted', 'Posted Invoice'),
            ('payment_received', 'Paid Invoice'),
        ],
        string='Earned On',
        default='invoice_posted',
        required=True,
        help='When a salesperson earns the commission.\n'
             '- Confirmed Sales Order: as soon as the order is confirmed.\n'
             '- Posted Invoice: once the invoice is posted.\n'
             '- Paid Invoice: only after the customer has actually paid.',
    )
    base_on = fields.Selection(
        selection=[
            ('revenue', 'Revenue'),
            ('margin', 'Margin'),
        ],
        string='Calculated On',
        default='revenue',
        required=True,
        help='Revenue pays on what was sold. Margin pays on what was made, so '
             'discounting into a loss stops paying commission.',
    )

    rule_ids = fields.One2many(
        comodel_name='eaglepub.commission.rule',
        inverse_name='plan_id',
        string='Rules',
    )
    user_ids = fields.One2many(
        comodel_name='res.users',
        inverse_name='eaglepub_commission_plan_id',
        string='Salespeople',
    )
    user_count = fields.Integer(compute='_compute_user_count', string='# Salespeople')

    @api.depends('user_ids')
    def _compute_user_count(self):
        for plan in self:
            plan.user_count = len(plan.user_ids)

    def rule_for_product(self, product):
        """First rule that matches, in sequence order.

        Ordering is the whole point: put the exceptions above the general case
        and the general case becomes a fallback rather than a conflict.
        """
        self.ensure_one()
        for rule in self.rule_ids.sorted(lambda r: (r.sequence, r.id)):
            if rule.matches(product):
                return rule
        return self.env['eaglepub.commission.rule']


class EaglepubCommissionRule(models.Model):
    _name = 'eaglepub.commission.rule'
    _description = 'Commission Rule'
    _order = 'sequence, id'

    plan_id = fields.Many2one(
        comodel_name='eaglepub.commission.plan',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)

    applies_to = fields.Selection(
        selection=[
            ('all', 'Everything'),
            ('product', 'One Product'),
            ('category', 'Product Category'),
        ],
        default='all',
        required=True,
    )
    product_id = fields.Many2one('product.product', string='Product')
    categ_id = fields.Many2one('product.category', string='Category')
    rate = fields.Float(
        string='Rate (%)',
        default=0.0,
        required=True,
        help='Percentage of the base amount paid as commission.',
    )

    _rate_range = models.Constraint(
        'CHECK(rate >= 0 AND rate <= 100)',
        'A commission rate must be between 0 and 100 percent.',
    )

    @api.onchange('applies_to')
    def _onchange_applies_to(self):
        if self.applies_to != 'product':
            self.product_id = False
        if self.applies_to != 'category':
            self.categ_id = False

    def matches(self, product):
        """Does this rule cover the given product?

        A category rule covers child categories too, which is what people mean
        when they set a rate on 'Furniture'.
        """
        self.ensure_one()
        if self.applies_to == 'all':
            return True
        if self.applies_to == 'product':
            return bool(product) and product == self.product_id
        if self.applies_to == 'category':
            if not product or not self.categ_id:
                return False
            categ = product.categ_id
            while categ:
                if categ == self.categ_id:
                    return True
                categ = categ.parent_id
        return False

    @api.depends('applies_to', 'product_id', 'categ_id', 'rate')
    def _compute_display_name(self):
        for rule in self:
            if rule.applies_to == 'product':
                what = rule.product_id.display_name or 'Product'
            elif rule.applies_to == 'category':
                what = rule.categ_id.display_name or 'Category'
            else:
                what = 'Everything'
            rule.display_name = '%s - %.2f%%' % (what, rule.rate)
