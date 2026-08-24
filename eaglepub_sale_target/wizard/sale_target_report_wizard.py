import base64
import io
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:  # pragma: no cover - xlsxwriter ships with Odoo
    xlsxwriter = None


QUARTERS = [('1', 'Q1'), ('2', 'Q2'), ('3', 'Q3'), ('4', 'Q4')]

MEASURED_LABELS = {
    'sale_order': 'Sale Orders',
    'invoice': 'Invoices',
}


class SaleTargetReportWizard(models.TransientModel):
    _name = 'sale.target.report.wizard'
    _description = 'Sales Target Report Wizard'

    period_type = fields.Selection(
        [
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
            ('custom', 'Custom Period'),
        ],
        string='Period',
        required=True,
        default='quarterly',
    )
    year = fields.Integer(
        string='Year',
        default=lambda self: fields.Date.context_today(self).year,
    )
    quarter = fields.Selection(
        QUARTERS,
        string='Quarter',
        default=lambda self: str((fields.Date.context_today(self).month - 1) // 3 + 1),
    )
    date_from = fields.Date(
        string='From', required=True,
        # precompute is required: the field is required (NOT NULL), and without
        # it Odoo inserts the row before running the compute.
        compute='_compute_period_dates', store=True, readonly=False,
        precompute=True,
    )
    date_to = fields.Date(
        string='To', required=True,
        compute='_compute_period_dates', store=True, readonly=False,
        precompute=True,
    )
    salesperson_ids = fields.Many2many(
        'res.users',
        string='Salespeople',
        domain=[('share', '=', False)],
        help='Leave empty to include every salesperson.',
    )
    team_ids = fields.Many2many(
        'crm.team',
        string='Sales Teams',
        help='Leave empty to include every team.',
    )
    product_ids = fields.Many2many(
        'product.product',
        string='Products',
        help='Leave empty to include every product.',
    )
    measured_on = fields.Selection(
        [
            ('all', 'Both'),
            ('sale_order', 'Sale Orders only'),
            ('invoice', 'Invoices only'),
        ],
        string='Measured On',
        required=True,
        default='all',
        help='Target lines are measured either on confirmed sale orders or on '
             'posted invoices. Restrict the report to one of them, or report '
             'both together.',
    )
    target_scope = fields.Selection(
        [
            ('sales', 'Sales Target'),
            ('material', 'Material Movement'),
        ],
        string='Scope',
        required=True,
        default='sales',
        help='Which set of targets to report on. Defaulted from the menu the '
             'report was opened from.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    xlsx_file = fields.Binary(string='XLSX File', readonly=True)
    xlsx_filename = fields.Char(string='XLSX Filename', readonly=True)

    @api.depends('period_type', 'year', 'quarter')
    def _compute_period_dates(self):
        """Derive the reporting range on the server.

        A compute rather than an onchange: the date fields are readonly in the
        form for every period type except Custom, and the web client does not
        send readonly values back, so an onchange would update the screen while
        the server filtered on its defaults.
        """
        for wiz in self:
            today = fields.Date.context_today(wiz)
            year = wiz.year or today.year
            if wiz.period_type == 'yearly':
                wiz.date_from = date(year, 1, 1)
                wiz.date_to = date(year, 12, 31)
            elif wiz.period_type == 'quarterly':
                quarter = int(wiz.quarter or ((today.month - 1) // 3 + 1))
                start = date(year, (quarter - 1) * 3 + 1, 1)
                wiz.date_from = start
                wiz.date_to = start + relativedelta(months=3, days=-1)
            elif not (wiz.date_from and wiz.date_to):
                # Custom, nothing chosen yet: seed with the current quarter.
                start = today.replace(month=((today.month - 1) // 3) * 3 + 1,
                                      day=1)
                wiz.date_from = start
                wiz.date_to = start + relativedelta(months=3, days=-1)

    # ─────────────────── Aggregation ───────────────────

    def _get_target_lines(self):
        """Target lines in scope, ordered by assignee then product.

        A target counts when its whole period sits inside the requested range,
        so asking for Q1 returns the targets that are about Q1 rather than
        slicing a yearly target down to three months of it.
        """
        self.ensure_one()
        domain = [
            ('date_start', '>=', self.date_from),
            ('date_end', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
            # Without this a Sales report would quietly total material
            # movement targets into its figures.
            ('target_scope', '=', self.target_scope),
        ]
        # Salesperson and team targets are alternatives, so selecting both
        # kinds of filter has to widen the result rather than narrow it away.
        assignee = []
        if self.salesperson_ids:
            assignee.append(('salesperson_id', 'in', self.salesperson_ids.ids))
        if self.team_ids:
            assignee.append(('team_id', 'in', self.team_ids.ids))
        if len(assignee) == 2:
            domain += ['|'] + assignee
        elif assignee:
            domain += assignee

        lines = self.env['sale.target'].search(domain).mapped('line_ids')
        if self.product_ids:
            lines = lines.filtered(lambda l: l.product_id in self.product_ids)
        if self.measured_on != 'all':
            lines = lines.filtered(lambda l: l.measured_on == self.measured_on)
        return lines.sorted(
            key=lambda l: (l._report_assignee_name(),
                           l.product_id.display_name or '',
                           l.target_id.date_start))

    @staticmethod
    def _group_percentage(bucket):
        """Achievement for a group of lines.

        Quantity driven: targets are set in quantity, so value is reported
        alongside but never drives the percentage.
        """
        if bucket['target_qty']:
            return (bucket['achieved_qty'] / bucket['target_qty']) * 100.0
        return 0.0

    def _get_report_data(self):
        """Single aggregation shared by the on-screen, PDF and XLSX outputs."""
        self.ensure_one()
        currency = self.company_id.currency_id
        groups = {}

        for line in self._get_target_lines():
            target = line.target_id
            key = (target.assign_to,
                   target.salesperson_id.id or target.team_id.id)
            bucket = groups.setdefault(key, {
                'assignee': line._report_assignee_name(),
                'assign_to': target.assign_to,
                'user_id': target.salesperson_id.id,
                'team_id': target.team_id.id,
                'lines': [],
                'target_qty': 0.0,
                'achieved_qty': 0.0,
                'target_amount': 0.0,
                'achieved_amount': 0.0,
            })

            bucket['lines'].append({
                'product': line.product_id.display_name,
                'product_id': line.product_id.id,
                'measured_on': line.measured_on,
                'measured_label': MEASURED_LABELS.get(line.measured_on, ''),
                'uom': (line.uom_id or line.product_id.uom_id).display_name,
                'period': f'{target.date_start} → {target.date_end}',
                'date_start': target.date_start,
                'date_end': target.date_end,
                'target_qty': line.target_qty,
                'achieved_qty': line.achieved_qty,
                'variance_qty': line.achieved_qty - line.target_qty,
                'target_amount': line.amount_untaxed,
                'achieved_amount': line.achieved_amount,
                'variance_amount': line.achieved_amount - line.amount_untaxed,
                'percentage': line.achieved_percentage,
            })
            bucket['target_qty'] += line.target_qty
            bucket['achieved_qty'] += line.achieved_qty
            bucket['target_amount'] += line.amount_untaxed
            bucket['achieved_amount'] += line.achieved_amount

        group_list = sorted(groups.values(), key=lambda g: g['assignee'])
        for bucket in group_list:
            bucket['variance_qty'] = bucket['achieved_qty'] - bucket['target_qty']
            bucket['variance_amount'] = (bucket['achieved_amount']
                                         - bucket['target_amount'])
            bucket['percentage'] = self._group_percentage(bucket)

        total = {
            'target_qty': sum(g['target_qty'] for g in group_list),
            'achieved_qty': sum(g['achieved_qty'] for g in group_list),
            'target_amount': sum(g['target_amount'] for g in group_list),
            'achieved_amount': sum(g['achieved_amount'] for g in group_list),
        }
        total['variance_qty'] = total['achieved_qty'] - total['target_qty']
        total['variance_amount'] = (total['achieved_amount']
                                    - total['target_amount'])
        total['percentage'] = self._group_percentage(total)

        return {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'company': self.company_id.display_name,
            'currency': currency,
            'salesperson_filter': ', '.join(
                self.salesperson_ids.mapped('name')) or _('All'),
            'team_filter': ', '.join(self.team_ids.mapped('name')) or _('All'),
            'product_filter': ', '.join(
                self.product_ids.mapped('display_name')) or _('All'),
            'scope_filter': dict(
                self._fields['target_scope'].selection).get(self.target_scope, ''),
            'measured_filter': dict(
                self._fields['measured_on'].selection).get(self.measured_on, ''),
            'groups': group_list,
            'total': total,
        }

    def _check_has_data(self, data):
        if not data['groups']:
            raise UserError(_(
                'No targets in this scope fall entirely inside '
                '%(start)s - %(end)s for the selected filters.',
                start=self.date_from, end=self.date_to,
            ))

    # ─────────────────── Outputs ───────────────────

    def action_view(self):
        """Materialise the rows and open them as a list/pivot view."""
        self.ensure_one()
        data = self._get_report_data()
        self._check_has_data(data)

        result_model = self.env['sale.target.report.line']
        result_model.search([('wizard_id', '=', self.id)]).unlink()
        result_model.create([{
            'wizard_id': self.id,
            'user_id': bucket['user_id'],
            'team_id': bucket['team_id'],
            'assign_to': bucket['assign_to'],
            'product_id': row['product_id'],
            'measured_on': row['measured_on'],
            'date_start': row['date_start'],
            'date_end': row['date_end'],
            'currency_id': self.company_id.currency_id.id,
            'target_qty': row['target_qty'],
            'achieved_qty': row['achieved_qty'],
            'variance_qty': row['variance_qty'],
            'target_amount': row['target_amount'],
            'achieved_amount': row['achieved_amount'],
            'variance_amount': row['variance_amount'],
            'percentage': row['percentage'],
        } for bucket in data['groups'] for row in bucket['lines']])

        action = self.env['ir.actions.act_window']._for_xml_id(
            'eaglepub_sale_target.sale_target_report_line_action')
        action['domain'] = [('wizard_id', '=', self.id)]
        action['display_name'] = _(
            'Sales Targets %(start)s - %(end)s',
            start=self.date_from, end=self.date_to)
        return action

    def action_print_pdf(self):
        self.ensure_one()
        self._check_has_data(self._get_report_data())
        return self.env.ref(
            'eaglepub_sale_target.action_report_sale_target'
        ).report_action(self)

    def action_export_xlsx(self):
        self.ensure_one()
        if xlsxwriter is None:
            raise UserError(_('The xlsxwriter library is not available.'))
        data = self._get_report_data()
        self._check_has_data(data)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        self._write_xlsx(workbook, data)
        workbook.close()

        filename = 'sales_target_report_%s_%s.xlsx' % (
            self.date_from, self.date_to)
        self.write({
            'xlsx_file': base64.b64encode(output.getvalue()),
            'xlsx_filename': filename,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s/%s/xlsx_file/%s?download=true' % (
                self._name, self.id, filename),
            'target': 'self',
        }

    def _write_xlsx(self, workbook, data):
        """Lay out the workbook: title block, then assignee groups with subtotals."""
        sheet = workbook.add_worksheet(_('Sales Targets'))
        sheet.set_landscape()
        sheet.freeze_panes(7, 0)

        title = workbook.add_format({
            'bold': True, 'font_size': 15, 'align': 'center',
            'valign': 'vcenter',
        })
        meta = workbook.add_format({'font_size': 9, 'italic': True})
        header = workbook.add_format({
            'bold': True, 'bg_color': '#1e5128', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'text_wrap': True,
        })
        group_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#dfe6e9', 'border': 1,
        })
        text = workbook.add_format({'border': 1})
        num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        pct = workbook.add_format({'border': 1, 'num_format': '0.0"%"'})
        sub_text = workbook.add_format({'bold': True, 'border': 1,
                                        'bg_color': '#f1f3f5'})
        sub_num = workbook.add_format({'bold': True, 'border': 1,
                                       'bg_color': '#f1f3f5',
                                       'num_format': '#,##0.00'})
        sub_pct = workbook.add_format({'bold': True, 'border': 1,
                                       'bg_color': '#f1f3f5',
                                       'num_format': '0.0"%"'})
        tot_text = workbook.add_format({'bold': True, 'border': 1,
                                        'bg_color': '#1e5128',
                                        'font_color': 'white'})
        tot_num = workbook.add_format({'bold': True, 'border': 1,
                                       'bg_color': '#1e5128',
                                       'font_color': 'white',
                                       'num_format': '#,##0.00'})
        tot_pct = workbook.add_format({'bold': True, 'border': 1,
                                       'bg_color': '#1e5128',
                                       'font_color': 'white',
                                       'num_format': '0.0"%"'})

        widths = [32, 14, 22, 12, 12, 12, 14, 14, 14, 10]
        for col, width in enumerate(widths):
            sheet.set_column(col, col, width)

        sheet.merge_range(0, 0, 0, 9, data['scope_filter'] and
                          '%s - %s' % (_('Target Report'), data['scope_filter'])
                          or _('Target Report'), title)
        sheet.write(1, 0, '%s: %s → %s' % (_('Period'), data['date_from'],
                                           data['date_to']), meta)
        sheet.write(2, 0, '%s: %s  |  %s: %s' % (
            _('Salespeople'), data['salesperson_filter'],
            _('Teams'), data['team_filter']), meta)
        sheet.write(3, 0, '%s: %s' % (_('Products'), data['product_filter']), meta)
        sheet.write(4, 0, '%s: %s  |  %s: %s  |  %s: %s' % (
            _('Scope'), data['scope_filter'],
            _('Measured on'), data['measured_filter'],
            _('Company'), data['company']), meta)

        columns = [
            _('Product'), _('Measured On'), _('Period'), _('Target Qty'),
            _('Achieved Qty'), _('Variance Qty'), _('Target Value'),
            _('Achieved Value'), _('Variance Value'), _('Achieved %'),
        ]
        row_idx = 6
        for col, name in enumerate(columns):
            sheet.write(row_idx, col, name, header)
        sheet.set_row(row_idx, 28)
        row_idx += 1

        for bucket in data['groups']:
            sheet.merge_range(row_idx, 0, row_idx, 9, bucket['assignee'],
                              group_fmt)
            row_idx += 1

            for row in bucket['lines']:
                sheet.write(row_idx, 0, row['product'], text)
                sheet.write(row_idx, 1, row['measured_label'], text)
                sheet.write(row_idx, 2, row['period'], text)
                sheet.write_number(row_idx, 3, row['target_qty'], num)
                sheet.write_number(row_idx, 4, row['achieved_qty'], num)
                sheet.write_number(row_idx, 5, row['variance_qty'], num)
                sheet.write_number(row_idx, 6, row['target_amount'], num)
                sheet.write_number(row_idx, 7, row['achieved_amount'], num)
                sheet.write_number(row_idx, 8, row['variance_amount'], num)
                sheet.write_number(row_idx, 9, row['percentage'], pct)
                row_idx += 1

            sheet.write(row_idx, 0, '%s %s' % (_('Subtotal'), bucket['assignee']),
                        sub_text)
            sheet.write(row_idx, 1, '', sub_text)
            sheet.write(row_idx, 2, '', sub_text)
            sheet.write_number(row_idx, 3, bucket['target_qty'], sub_num)
            sheet.write_number(row_idx, 4, bucket['achieved_qty'], sub_num)
            sheet.write_number(row_idx, 5, bucket['variance_qty'], sub_num)
            sheet.write_number(row_idx, 6, bucket['target_amount'], sub_num)
            sheet.write_number(row_idx, 7, bucket['achieved_amount'], sub_num)
            sheet.write_number(row_idx, 8, bucket['variance_amount'], sub_num)
            sheet.write_number(row_idx, 9, bucket['percentage'], sub_pct)
            row_idx += 2

        total = data['total']
        sheet.write(row_idx, 0, _('Grand Total'), tot_text)
        sheet.write(row_idx, 1, '', tot_text)
        sheet.write(row_idx, 2, '', tot_text)
        sheet.write_number(row_idx, 3, total['target_qty'], tot_num)
        sheet.write_number(row_idx, 4, total['achieved_qty'], tot_num)
        sheet.write_number(row_idx, 5, total['variance_qty'], tot_num)
        sheet.write_number(row_idx, 6, total['target_amount'], tot_num)
        sheet.write_number(row_idx, 7, total['achieved_amount'], tot_num)
        sheet.write_number(row_idx, 8, total['variance_amount'], tot_num)
        sheet.write_number(row_idx, 9, total['percentage'], tot_pct)


class SaleTargetReportLine(models.TransientModel):
    _name = 'sale.target.report.line'
    _description = 'Sales Target Report Line'
    _order = 'user_id, team_id, product_id, date_start'

    wizard_id = fields.Many2one(
        'sale.target.report.wizard', string='Wizard',
        ondelete='cascade', index=True,
    )
    user_id = fields.Many2one('res.users', string='Salesperson')
    team_id = fields.Many2one('crm.team', string='Sales Team')
    assign_to = fields.Selection(
        [('salesperson', 'Salesperson'), ('team', 'Sales Team')],
        string='Assigned To',
    )
    product_id = fields.Many2one('product.product', string='Product')
    measured_on = fields.Selection(
        [('sale_order', 'Sale Orders'), ('invoice', 'Invoices')],
        string='Measured On',
    )
    date_start = fields.Date(string='Period Start')
    date_end = fields.Date(string='Period End')
    currency_id = fields.Many2one('res.currency', string='Currency')

    target_qty = fields.Float(string='Target Qty',
                              digits='Product Unit of Measure')
    achieved_qty = fields.Float(string='Achieved Qty',
                                digits='Product Unit of Measure')
    variance_qty = fields.Float(string='Variance Qty',
                                digits='Product Unit of Measure')
    target_amount = fields.Monetary(string='Target Value',
                                    currency_field='currency_id')
    achieved_amount = fields.Monetary(string='Achieved Value',
                                      currency_field='currency_id')
    variance_amount = fields.Monetary(string='Variance Value',
                                      currency_field='currency_id')
    percentage = fields.Float(string='Achieved %')
