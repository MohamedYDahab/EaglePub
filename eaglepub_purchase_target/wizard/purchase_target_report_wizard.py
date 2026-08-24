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


class PurchaseTargetReportWizard(models.TransientModel):
    _name = 'purchase.target.report.wizard'
    _description = 'Purchase Target Report Wizard'

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
        # precompute is required: the field is required (NOT NULL), and without
        # it Odoo inserts the row before running the compute.
        compute='_compute_period_dates', store=True, readonly=False,
        precompute=True,
    )
    partner_ids = fields.Many2many(
        'res.partner',
        string='Vendors',
        help='Leave empty to include every vendor.',
    )
    product_ids = fields.Many2many(
        'product.product',
        string='Products',
        help='Leave empty to include every product.',
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

        This has to be a compute rather than an onchange. The date fields are
        readonly in the form for every period type except Custom, and the web
        client does not send readonly values back -- so an onchange updated the
        screen while the server kept its defaults, and quarterly or yearly runs
        silently reported a different period than the one displayed.

        readonly=False keeps Custom editable; an explicit write still wins.
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
        """Target lines in scope, ordered by vendor then product.

        A target counts when its whole period sits inside the requested range,
        so asking for Q1 returns the targets that are about Q1 rather than
        slicing a yearly target down to three months of it.
        """
        self.ensure_one()
        domain = [
            ('date_start', '>=', self.date_from),
            ('date_end', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
        ]
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))

        targets = self.env['purchase.target'].search(domain)
        lines = targets.mapped('line_ids')
        if self.product_ids:
            lines = lines.filtered(lambda l: l.product_id in self.product_ids)
        return lines.sorted(
            key=lambda l: (l.target_id.partner_id.name or '',
                           l.product_id.display_name or '',
                           l.target_id.date_start))

    @staticmethod
    def _group_percentage(bucket):
        """Achievement for a group of lines.

        Quantity driven throughout: targets are set in quantity, so value is
        reported alongside but never drives the percentage.
        """
        if bucket['target_qty']:
            return (bucket['achieved_qty'] / bucket['target_qty']) * 100.0
        return 0.0

    def _get_report_data(self):
        """Single aggregation shared by the on-screen, PDF and XLSX outputs."""
        self.ensure_one()
        currency = self.company_id.currency_id
        vendors = {}

        for line in self._get_target_lines():
            target = line.target_id
            partner = target.partner_id
            bucket = vendors.setdefault(partner.id, {
                'partner_id': partner.id,
                'vendor': partner.display_name,
                'lines': [],
                'target_qty': 0.0,
                'achieved_qty': 0.0,
                'target_amount': 0.0,
                'achieved_amount': 0.0,
            })

            row = {
                'product': line.product_id.display_name,
                'product_id': line.product_id.id,
                'uom': (line.uom_id or line.product_id.uom_id).display_name,

                'period': f'{target.date_start} → {target.date_end}',
                'date_start': target.date_start,
                'date_end': target.date_end,
                'target_qty': line.target_qty,
                'achieved_qty': line.achieved_qty,
                'variance_qty': line.achieved_qty - line.target_qty,
                'target_amount': line.amount_untaxed,
                'achieved_amount': line.achieved_amount,
                'variance_amount': (line.achieved_amount
                                    - line.amount_untaxed),
                'percentage': line.achieved_percentage,
            }
            bucket['lines'].append(row)
            bucket['target_qty'] += line.target_qty
            bucket['achieved_qty'] += line.achieved_qty
            bucket['target_amount'] += line.amount_untaxed
            bucket['achieved_amount'] += line.achieved_amount

        vendor_list = sorted(vendors.values(), key=lambda v: v['vendor'])
        for bucket in vendor_list:
            bucket['variance_qty'] = bucket['achieved_qty'] - bucket['target_qty']
            bucket['variance_amount'] = (bucket['achieved_amount']
                                         - bucket['target_amount'])
            bucket['percentage'] = self._group_percentage(bucket)

        total = {
            'target_qty': sum(v['target_qty'] for v in vendor_list),
            'achieved_qty': sum(v['achieved_qty'] for v in vendor_list),
            'target_amount': sum(v['target_amount'] for v in vendor_list),
            'achieved_amount': sum(v['achieved_amount'] for v in vendor_list),
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
            'currency_symbol': currency.symbol or currency.name,
            'vendor_filter': ', '.join(self.partner_ids.mapped('display_name')) or _('All'),
            'product_filter': ', '.join(self.product_ids.mapped('display_name')) or _('All'),
            'vendors': vendor_list,
            'total': total,
        }

    def _check_has_data(self, data):
        if not data['vendors']:
            raise UserError(_(
                'No purchase targets fall entirely inside %(start)s - %(end)s '
                'for the selected filters.',
                start=self.date_from, end=self.date_to,
            ))

    # ─────────────────── Outputs ───────────────────

    def action_view(self):
        """Materialise the rows and open them as a list/pivot view."""
        self.ensure_one()
        data = self._get_report_data()
        self._check_has_data(data)

        result_model = self.env['purchase.target.report.line']
        result_model.search([('wizard_id', '=', self.id)]).unlink()

        vals_list = []
        for bucket in data['vendors']:
            for row in bucket['lines']:
                vals_list.append({
                    'wizard_id': self.id,
                    'partner_id': bucket['partner_id'],
                    'product_id': row['product_id'],
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
                })
        result_model.create(vals_list)

        action = self.env['ir.actions.act_window']._for_xml_id(
            'eaglepub_purchase_target.purchase_target_report_line_action')
        action['domain'] = [('wizard_id', '=', self.id)]
        action['display_name'] = _(
            'Purchase Targets %(start)s - %(end)s',
            start=self.date_from, end=self.date_to)
        return action

    def action_print_pdf(self):
        self.ensure_one()
        self._check_has_data(self._get_report_data())
        return self.env.ref(
            'eaglepub_purchase_target.action_report_purchase_target'
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

        filename = 'purchase_target_report_%s_%s.xlsx' % (
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
        """Lay out the workbook: title block, then vendor groups with subtotals."""
        sheet = workbook.add_worksheet(_('Purchase Targets'))
        sheet.set_landscape()
        sheet.freeze_panes(6, 0)

        title = workbook.add_format({
            'bold': True, 'font_size': 15, 'align': 'center',
            'valign': 'vcenter',
        })
        meta = workbook.add_format({'font_size': 9, 'italic': True})
        header = workbook.add_format({
            'bold': True, 'bg_color': '#2c3e50', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'text_wrap': True,
        })
        vendor_fmt = workbook.add_format({
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
                                        'bg_color': '#2c3e50',
                                        'font_color': 'white'})
        tot_num = workbook.add_format({'bold': True, 'border': 1,
                                       'bg_color': '#2c3e50',
                                       'font_color': 'white',
                                       'num_format': '#,##0.00'})
        tot_pct = workbook.add_format({'bold': True, 'border': 1,
                                       'bg_color': '#2c3e50',
                                       'font_color': 'white',
                                       'num_format': '0.0"%"'})

        widths = [34, 22, 12, 12, 12, 14, 14, 14, 10]
        for col, width in enumerate(widths):
            sheet.set_column(col, col, width)

        sheet.merge_range(0, 0, 0, 8, _('Purchase Target Report'), title)
        sheet.write(1, 0, '%s: %s → %s' % (_('Period'), data['date_from'],
                                           data['date_to']), meta)
        sheet.write(2, 0, '%s: %s' % (_('Vendors'), data['vendor_filter']), meta)
        sheet.write(3, 0, '%s: %s' % (_('Products'), data['product_filter']), meta)
        sheet.write(4, 0, '%s: %s (%s)' % (_('Company'), data['company'],
                                           data['currency_symbol']), meta)

        columns = [
            _('Product'), _('Period'), _('Target Qty'), _('Received Qty'),
            _('Variance Qty'), _('Target Value'), _('Received Value'),
            _('Variance Value'), _('Achieved %'),
        ]
        row_idx = 5
        for col, name in enumerate(columns):
            sheet.write(row_idx, col, name, header)
        sheet.set_row(row_idx, 28)
        row_idx += 1

        for bucket in data['vendors']:
            sheet.merge_range(row_idx, 0, row_idx, 8, bucket['vendor'],
                              vendor_fmt)
            row_idx += 1

            for row in bucket['lines']:
                sheet.write(row_idx, 0, row['product'], text)
                sheet.write(row_idx, 1, row['period'], text)
                sheet.write_number(row_idx, 2, row['target_qty'], num)
                sheet.write_number(row_idx, 3, row['achieved_qty'], num)
                sheet.write_number(row_idx, 4, row['variance_qty'], num)
                sheet.write_number(row_idx, 5, row['target_amount'], num)
                sheet.write_number(row_idx, 6, row['achieved_amount'], num)
                sheet.write_number(row_idx, 7, row['variance_amount'], num)
                sheet.write_number(row_idx, 8, row['percentage'], pct)
                row_idx += 1

            sheet.write(row_idx, 0, '%s %s' % (_('Subtotal'), bucket['vendor']),
                        sub_text)
            sheet.write(row_idx, 1, '', sub_text)
            sheet.write_number(row_idx, 2, bucket['target_qty'], sub_num)
            sheet.write_number(row_idx, 3, bucket['achieved_qty'], sub_num)
            sheet.write_number(row_idx, 4, bucket['variance_qty'], sub_num)
            sheet.write_number(row_idx, 5, bucket['target_amount'], sub_num)
            sheet.write_number(row_idx, 6, bucket['achieved_amount'], sub_num)
            sheet.write_number(row_idx, 7, bucket['variance_amount'], sub_num)
            sheet.write_number(row_idx, 8, bucket['percentage'], sub_pct)
            row_idx += 2

        total = data['total']
        sheet.write(row_idx, 0, _('Grand Total'), tot_text)
        sheet.write(row_idx, 1, '', tot_text)
        sheet.write_number(row_idx, 2, total['target_qty'], tot_num)
        sheet.write_number(row_idx, 3, total['achieved_qty'], tot_num)
        sheet.write_number(row_idx, 4, total['variance_qty'], tot_num)
        sheet.write_number(row_idx, 5, total['target_amount'], tot_num)
        sheet.write_number(row_idx, 6, total['achieved_amount'], tot_num)
        sheet.write_number(row_idx, 7, total['variance_amount'], tot_num)
        sheet.write_number(row_idx, 8, total['percentage'], tot_pct)


class PurchaseTargetReportLine(models.TransientModel):
    _name = 'purchase.target.report.line'
    _description = 'Purchase Target Report Line'
    _order = 'partner_id, product_id, date_start'

    wizard_id = fields.Many2one(
        'purchase.target.report.wizard',
        string='Wizard',
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one('res.partner', string='Vendor')
    product_id = fields.Many2one('product.product', string='Product')
    date_start = fields.Date(string='Period Start')
    date_end = fields.Date(string='Period End')
    currency_id = fields.Many2one('res.currency', string='Currency')

    target_qty = fields.Float(string='Target Qty',
                              digits='Product Unit of Measure')
    achieved_qty = fields.Float(string='Received Qty',
                                digits='Product Unit of Measure')
    variance_qty = fields.Float(string='Variance Qty',
                                digits='Product Unit of Measure')
    target_amount = fields.Monetary(string='Target Amount',
                                    currency_field='currency_id')
    achieved_amount = fields.Monetary(string='Received Amount',
                                      currency_field='currency_id')
    variance_amount = fields.Monetary(string='Variance Amount',
                                      currency_field='currency_id')
    percentage = fields.Float(string='Achieved %')
