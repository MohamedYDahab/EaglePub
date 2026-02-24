# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


MONTH_SELECTION = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'),
    ('4', 'April'), ('5', 'May'), ('6', 'June'),
    ('7', 'July'), ('8', 'August'), ('9', 'September'),
    ('10', 'October'), ('11', 'November'), ('12', 'December'),
]


class CopyTargetWizard(models.TransientModel):
    _name = 'copy.target.wizard'
    _description = 'Copy Targets Wizard'

    target_type = fields.Selection([
        ('all', 'All Types'),
        ('salesperson', 'Salesperson Only'),
        ('pos', 'Point of Sale Only'),
    ], string='Target Type', required=True, default='all')

    # Source
    source_month = fields.Selection(
        MONTH_SELECTION, string='From Month', required=True,
    )
    source_year = fields.Integer(
        string='From Year', required=True,
        default=lambda self: fields.Date.today().year,
    )

    # Destination
    dest_month = fields.Selection(
        MONTH_SELECTION, string='To Month', required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    dest_year = fields.Integer(
        string='To Year', required=True,
        default=lambda self: fields.Date.today().year,
    )

    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    adjustment_percent = fields.Float(
        string='Adjustment %', default=0,
        help='Increase or decrease target amounts. '
             'E.g. 10 = +10%, -5 = -5%.',
    )
    skip_existing = fields.Boolean(
        string='Skip Existing Targets', default=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.today()
        if today.month == 1:
            res['source_month'] = '12'
            res['source_year'] = today.year - 1
        else:
            res['source_month'] = str(today.month - 1)
            res['source_year'] = today.year
        return res

    def action_copy_targets(self):
        self.ensure_one()

        if (self.source_month == self.dest_month
                and self.source_year == self.dest_year):
            raise UserError(_(
                'Source and destination months must be different.'))

        domain = [
            ('month', '=', self.source_month),
            ('year', '=', self.source_year),
            ('company_id', '=', self.company_id.id),
        ]
        if self.target_type != 'all':
            domain.append(('target_type', '=', self.target_type))

        source_targets = self.env['sales.target'].search(domain)
        if not source_targets:
            raise UserError(_(
                'No targets found for the source month.'))

        created = self.env['sales.target']
        multiplier = 1 + (self.adjustment_percent / 100)

        for st in source_targets:
            if self.skip_existing:
                dup_domain = [
                    ('target_type', '=', st.target_type),
                    ('month', '=', self.dest_month),
                    ('year', '=', self.dest_year),
                    ('company_id', '=', self.company_id.id),
                ]
                if st.target_type == 'salesperson':
                    dup_domain.append(('user_id', '=', st.user_id.id))
                else:
                    dup_domain.append(
                        ('pos_config_id', '=', st.pos_config_id.id))
                if self.env['sales.target'].search(dup_domain, limit=1):
                    continue

            vals = {
                'target_type': st.target_type,
                'month': self.dest_month,
                'year': self.dest_year,
                'target_amount': max(st.target_amount * multiplier, 0),
                'company_id': self.company_id.id,
            }
            if st.target_type == 'salesperson':
                vals['user_id'] = st.user_id.id
            else:
                vals['pos_config_id'] = st.pos_config_id.id

            created |= self.env['sales.target'].create(vals)

        if not created:
            raise UserError(_(
                'No new targets created. All already exist '
                'for the destination month.'))

        return {
            'name': _('Copied Targets'),
            'type': 'ir.actions.act_window',
            'res_model': 'sales.target',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
            'target': 'current',
        }
