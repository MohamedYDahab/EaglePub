# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


MONTH_SELECTION = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'),
    ('4', 'April'), ('5', 'May'), ('6', 'June'),
    ('7', 'July'), ('8', 'August'), ('9', 'September'),
    ('10', 'October'), ('11', 'November'), ('12', 'December'),
]


class BulkTargetWizard(models.TransientModel):
    _name = 'bulk.target.wizard'
    _description = 'Bulk Target Creation Wizard'

    target_type = fields.Selection([
        ('salesperson', 'Salesperson'),
        ('pos', 'Point of Sale'),
    ], string='Target Type', required=True, default='salesperson')
    month = fields.Selection(
        MONTH_SELECTION, string='Month', required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    year = fields.Integer(
        string='Year', required=True,
        default=lambda self: fields.Date.today().year,
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    team_id = fields.Many2one(
        'crm.team', string='Sales Team',
        help='Filter salespersons by team. Leave empty for all.',
    )
    line_ids = fields.One2many(
        'bulk.target.wizard.line', 'wizard_id', string='Targets',
    )

    @api.onchange('target_type', 'team_id', 'month', 'year', 'company_id')
    def _onchange_populate_lines(self):
        """Populate lines based on target type."""
        self.line_ids = [(5, 0, 0)]
        lines = []

        if self.target_type == 'salesperson':
            domain = [('share', '=', False)]
            if self.team_id:
                domain.append(('sale_team_id', '=', self.team_id.id))
            users = self.env['res.users'].search(domain)
            for user in users:
                existing = self.env['sales.target'].search([
                    ('target_type', '=', 'salesperson'),
                    ('user_id', '=', user.id),
                    ('month', '=', self.month),
                    ('year', '=', self.year),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)
                if not existing:
                    lines.append((0, 0, {
                        'user_id': user.id,
                        'target_amount': 0,
                    }))

        elif self.target_type == 'pos':
            configs = self.env['pos.config'].search([
                ('company_id', '=', self.company_id.id),
            ])
            for config in configs:
                existing = self.env['sales.target'].search([
                    ('target_type', '=', 'pos'),
                    ('pos_config_id', '=', config.id),
                    ('month', '=', self.month),
                    ('year', '=', self.year),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)
                if not existing:
                    lines.append((0, 0, {
                        'pos_config_id': config.id,
                        'target_amount': 0,
                    }))

        self.line_ids = lines

    def action_create_targets(self):
        """Create sales targets for all lines with amount > 0."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No items to create targets for.'))

        lines_with_amount = self.line_ids.filtered(
            lambda l: l.target_amount > 0)
        if not lines_with_amount:
            raise UserError(_(
                'Please set target amount for at least one entry.'))

        created = self.env['sales.target']
        for line in lines_with_amount:
            vals = {
                'target_type': self.target_type,
                'month': self.month,
                'year': self.year,
                'target_amount': line.target_amount,
                'company_id': self.company_id.id,
            }
            if self.target_type == 'salesperson':
                vals['user_id'] = line.user_id.id
                # Check duplicate
                dup_domain = [
                    ('target_type', '=', 'salesperson'),
                    ('user_id', '=', line.user_id.id),
                    ('month', '=', self.month),
                    ('year', '=', self.year),
                    ('company_id', '=', self.company_id.id),
                ]
            else:
                vals['pos_config_id'] = line.pos_config_id.id
                dup_domain = [
                    ('target_type', '=', 'pos'),
                    ('pos_config_id', '=', line.pos_config_id.id),
                    ('month', '=', self.month),
                    ('year', '=', self.year),
                    ('company_id', '=', self.company_id.id),
                ]

            if not self.env['sales.target'].search(dup_domain, limit=1):
                created |= self.env['sales.target'].create(vals)

        if not created:
            raise UserError(_(
                'All targets already exist for the selected period.'))

        return {
            'name': _('Created Targets'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.target',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created.ids)],
            'target': 'current',
        }


class BulkTargetWizardLine(models.TransientModel):
    _name = 'bulk.target.wizard.line'
    _description = 'Bulk Target Wizard Line'

    wizard_id = fields.Many2one(
        'bulk.target.wizard', ondelete='cascade',
    )
    user_id = fields.Many2one(
        'res.users', string='Salesperson',
    )
    pos_config_id = fields.Many2one(
        'pos.config', string='Point of Sale',
    )
    target_amount = fields.Float(string='Target Amount')
