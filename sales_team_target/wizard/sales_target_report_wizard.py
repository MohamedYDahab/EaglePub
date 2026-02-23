# -*- coding: utf-8 -*-
import io
import base64
import calendar
from datetime import date, datetime, time

from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


MONTH_SELECTION = [
    ('1', 'January'), ('2', 'February'), ('3', 'March'),
    ('4', 'April'), ('5', 'May'), ('6', 'June'),
    ('7', 'July'), ('8', 'August'), ('9', 'September'),
    ('10', 'October'), ('11', 'November'), ('12', 'December'),
]


class SalesTargetReportWizard(models.TransientModel):
    _name = 'sales.target.report.wizard'
    _description = 'Sales Target Report Wizard'

    target_type = fields.Selection([
        ('all', 'All Types'),
        ('salesperson', 'Salesperson Only'),
        ('pos', 'Point of Sale Only'),
    ], string='Target Type', required=True, default='all')

    date_from = fields.Date(
        string='Date From', required=True,
        default=lambda self: fields.Date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='Date To', required=True,
        default=lambda self: fields.Date.today(),
    )
    user_ids = fields.Many2many(
        'res.users', string='Salespersons',
        domain=[('share', '=', False)],
        help='Leave empty for all.',
    )
    pos_config_ids = fields.Many2many(
        'pos.config', string='Points of Sale',
        help='Leave empty for all.',
    )
    team_id = fields.Many2one(
        'crm.team', string='Sales Team',
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from > wiz.date_to:
                raise UserError(_(
                    'Date From cannot be greater than Date To.'))

    # ─────────────────── Translations ───────────────────

    def _get_translations(self):
        lang = self.env.user.lang or 'en_US'
        if lang.startswith('ar'):
            return {
                'report_title': 'تقرير أداء المبيعات',
                'company': 'الشركة',
                'period': 'الفترة',
                'to': 'إلى',
                'name': 'الاسم',
                'type': 'النوع',
                'target': 'المستهدف',
                'invoice_amount': 'مبلغ الفواتير',
                'pos_amount': 'مبلغ نقاط البيع',
                'achieved': 'المحقق',
                'ratio': 'نسبة الإنجاز %',
                'remaining': 'المتبقي',
                'reference': 'المرجع',
                'customer': 'العميل',
                'date': 'التاريخ',
                'amount': 'المبلغ',
                'source': 'المصدر',
                'totals': 'الإجمالي',
                'summary_sheet': 'الملخص',
                'detail_sheet': 'التفاصيل',
                'salesperson': 'مندوب المبيعات',
                'point_of_sale': 'نقطة البيع',
                'invoice': 'فاتورة',
                'credit_note': 'إشعار دائن',
                'pos_order': 'طلب نقطة البيع',
                'is_rtl': True,
            }
        return {
            'report_title': 'Sales Performance Report',
            'company': 'Company',
            'period': 'Period',
            'to': 'to',
            'name': 'Name',
            'type': 'Type',
            'target': 'Target',
            'invoice_amount': 'Invoice Amount',
            'pos_amount': 'POS Amount',
            'achieved': 'Achieved',
            'ratio': 'Achievement %',
            'remaining': 'Remaining',
            'reference': 'Reference',
            'customer': 'Customer',
            'date': 'Date',
            'amount': 'Amount',
            'source': 'Source',
            'totals': 'TOTALS',
            'summary_sheet': 'Summary',
            'detail_sheet': 'Details',
            'salesperson': 'Salesperson',
            'point_of_sale': 'Point of Sale',
            'invoice': 'Invoice',
            'credit_note': 'Credit Note',
            'pos_order': 'POS Order',
            'is_rtl': False,
        }

    # ─────────────────── Report Data ───────────────────

    def _get_month_keys_in_range(self):
        """Return set of (month_str, year) tuples covered by date range."""
        d_from = self.date_from
        d_to = self.date_to
        month_keys = set()
        current = d_from.replace(day=1)
        while current <= d_to:
            month_keys.add((str(current.month), current.year))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        return month_keys

    def _get_report_data(self):
        self.ensure_one()
        d_from = self.date_from
        d_to = self.date_to
        month_keys = self._get_month_keys_in_range()
        tr = self._get_translations()

        summary_lines = []
        detail_lines = []
        total_target = total_achieved = 0
        total_invoice = total_pos = 0

        source_labels = {
            'invoice': tr.get('invoice', 'Invoice'),
            'credit_note': tr.get('credit_note', 'Credit Note'),
            'pos': tr.get('pos_order', 'POS Order'),
        }

        # ── Salesperson targets ──
        if self.target_type in ('all', 'salesperson'):
            users = self._get_salesperson_list()
            for user in users.sorted(key=lambda u: u.name):
                row, details = self._build_salesperson_row(
                    user, d_from, d_to, month_keys, source_labels, tr)
                if row:
                    summary_lines.append(row)
                    detail_lines.extend(details)
                    total_target += row['target']
                    total_invoice += row['invoice_amount']
                    total_achieved += row['achieved']

        # ── POS targets ──
        if self.target_type in ('all', 'pos'):
            configs = self._get_pos_config_list()
            for config in configs.sorted(key=lambda c: c.name):
                row, details = self._build_pos_row(
                    config, d_from, d_to, month_keys, source_labels, tr)
                if row:
                    summary_lines.append(row)
                    detail_lines.extend(details)
                    total_target += row['target']
                    total_pos += row['pos_amount']
                    total_achieved += row['achieved']

        overall_ratio = ((total_achieved / total_target * 100)
                         if total_target else 0)

        return {
            'summary_lines': summary_lines,
            'detail_lines': detail_lines,
            'totals': {
                'target': total_target,
                'invoice_amount': total_invoice,
                'pos_amount': total_pos,
                'achieved': total_achieved,
                'ratio': overall_ratio,
                'remaining': total_target - total_achieved,
            },
            'date_from': d_from.strftime('%Y-%m-%d'),
            'date_to': d_to.strftime('%Y-%m-%d'),
            'company_name': self.company_id.name,
            'currency_symbol': self.currency_id.symbol,
        }

    def _get_salesperson_list(self):
        if self.user_ids:
            return self.user_ids
        domain = [('share', '=', False)]
        return self.env['res.users'].search(domain)

    def _get_pos_config_list(self):
        if self.pos_config_ids:
            return self.pos_config_ids
        return self.env['pos.config'].search([
            ('company_id', '=', self.company_id.id),
        ])

    def _build_salesperson_row(self, user, d_from, d_to,
                               month_keys, source_labels, tr):
        """Build summary row + details for one salesperson."""
        # Target total for covered months
        user_target = 0
        for month_str, year in month_keys:
            target = self.env['sales.target'].search([
                ('target_type', '=', 'salesperson'),
                ('user_id', '=', user.id),
                ('month', '=', month_str),
                ('year', '=', year),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if target:
                user_target += target.target_amount

        # Invoices
        invoices = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('invoice_user_id', '=', user.id),
            ('invoice_date', '>=', d_from),
            ('invoice_date', '<=', d_to),
            ('company_id', '=', self.company_id.id),
        ])
        inv_total = sum(invoices.mapped('amount_untaxed_signed'))

        details = []
        for inv in invoices:
            stype = ('invoice' if inv.move_type == 'out_invoice'
                     else 'credit_note')
            details.append({
                'name': user.name,
                'source': source_labels.get(stype, stype),
                'reference': inv.name,
                'customer': inv.partner_id.name or '',
                'date': (inv.invoice_date.strftime('%Y-%m-%d')
                         if inv.invoice_date else ''),
                'amount': inv.amount_untaxed_signed,
            })

        if not user_target and not inv_total:
            return None, []

        achieved = inv_total
        ratio = (achieved / user_target * 100) if user_target else 0
        row = {
            'name': user.name,
            'type': tr.get('salesperson', 'Salesperson'),
            'target': user_target,
            'invoice_amount': inv_total,
            'pos_amount': 0,
            'achieved': achieved,
            'ratio': ratio,
            'remaining': user_target - achieved,
        }
        return row, details

    def _build_pos_row(self, config, d_from, d_to,
                       month_keys, source_labels, tr):
        """Build summary row + details for one POS config."""
        pos_target = 0
        for month_str, year in month_keys:
            target = self.env['sales.target'].search([
                ('target_type', '=', 'pos'),
                ('pos_config_id', '=', config.id),
                ('month', '=', month_str),
                ('year', '=', year),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if target:
                pos_target += target.target_amount

        dt_from = datetime.combine(d_from, time.min)
        dt_to = datetime.combine(d_to, time.max)
        pos_orders = self.env['pos.order'].search([
            ('state', 'in', ['paid', 'done', 'invoiced']),
            ('config_id', '=', config.id),
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('company_id', '=', self.company_id.id),
        ])
        pos_total = (sum(pos_orders.mapped('amount_total'))
                     - sum(pos_orders.mapped('amount_tax')))

        details = []
        for po in pos_orders:
            details.append({
                'name': config.name,
                'source': source_labels['pos'],
                'reference': po.pos_reference or po.name,
                'customer': po.partner_id.name if po.partner_id else '',
                'date': (po.date_order.strftime('%Y-%m-%d')
                         if po.date_order else ''),
                'amount': po.amount_total - po.amount_tax,
            })

        if not pos_target and not pos_total:
            return None, []

        achieved = pos_total
        ratio = (achieved / pos_target * 100) if pos_target else 0
        row = {
            'name': config.name,
            'type': tr.get('point_of_sale', 'Point of Sale'),
            'target': pos_target,
            'invoice_amount': 0,
            'pos_amount': pos_total,
            'achieved': achieved,
            'ratio': ratio,
            'remaining': pos_target - achieved,
        }
        return row, details

    # ─────────────────── PDF ───────────────────

    def action_print_pdf(self):
        self.ensure_one()
        data = {'form': {
            'wizard_id': self.id,
            'date_from': self.date_from.strftime('%Y-%m-%d'),
            'date_to': self.date_to.strftime('%Y-%m-%d'),
            'target_type': self.target_type,
            'company_id': self.company_id.id,
        }}
        return self.env.ref(
            'sales_team_target.action_report_sales_target'
        ).report_action(self, data=data)

    # ─────────────────── Excel ───────────────────

    def action_export_excel(self):
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(_('xlsxwriter library is not installed.'))

        report_data = self._get_report_data()
        tr = self._get_translations()
        is_rtl = tr.get('is_rtl', False)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # ── Formats ──
        fmt_title = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center',
            'valign': 'vcenter', 'font_color': '#2c3e50',
        })
        fmt_info = workbook.add_format({
            'font_size': 10, 'italic': True,
            'align': 'right' if is_rtl else 'left',
        })
        fmt_header = workbook.add_format({
            'bold': True, 'font_size': 10, 'align': 'center',
            'valign': 'vcenter', 'bg_color': '#2c3e50',
            'font_color': 'white', 'border': 1, 'text_wrap': True,
        })
        fmt_cell = workbook.add_format({
            'font_size': 10, 'border': 1,
            'align': 'right' if is_rtl else 'left', 'valign': 'vcenter',
        })
        fmt_money = workbook.add_format({
            'font_size': 10, 'border': 1, 'num_format': '#,##0.00',
            'align': 'left' if is_rtl else 'right', 'valign': 'vcenter',
        })
        fmt_percent = workbook.add_format({
            'font_size': 10, 'border': 1, 'num_format': '0.00%',
            'align': 'center', 'valign': 'vcenter',
        })
        fmt_money_green = workbook.add_format({
            'font_size': 10, 'border': 1, 'num_format': '#,##0.00',
            'align': 'left' if is_rtl else 'right', 'valign': 'vcenter',
            'font_color': '#27ae60', 'bold': True,
        })
        fmt_money_red = workbook.add_format({
            'font_size': 10, 'border': 1, 'num_format': '#,##0.00',
            'align': 'left' if is_rtl else 'right', 'valign': 'vcenter',
            'font_color': '#e74c3c',
        })
        fmt_total_label = workbook.add_format({
            'bold': True, 'font_size': 11, 'border': 1,
            'align': 'left' if is_rtl else 'right', 'valign': 'vcenter',
            'bg_color': '#ecf0f1',
        })
        fmt_total = workbook.add_format({
            'bold': True, 'font_size': 11, 'border': 1,
            'num_format': '#,##0.00', 'bg_color': '#ecf0f1',
            'align': 'left' if is_rtl else 'right', 'valign': 'vcenter',
        })
        fmt_total_green = workbook.add_format({
            'bold': True, 'font_size': 11, 'border': 1,
            'num_format': '#,##0.00', 'bg_color': '#27ae60',
            'font_color': 'white',
            'align': 'left' if is_rtl else 'right', 'valign': 'vcenter',
        })

        # ═══════════ SUMMARY SHEET ═══════════
        ws1 = workbook.add_worksheet(tr['summary_sheet'][:31])
        if is_rtl:
            ws1.right_to_left()

        widths = [22, 16, 16, 16, 16, 16, 14, 16]
        for i, w in enumerate(widths):
            ws1.set_column(i, i, w)
        last_col = len(widths) - 1

        row = 0
        ws1.merge_range(row, 0, row, last_col,
                        tr['report_title'], fmt_title)
        row += 1
        ws1.write(row, 0,
                  f"{tr['company']}: {report_data['company_name']}",
                  fmt_info)
        row += 1
        ws1.write(row, 0,
                  f"{tr['period']}: {report_data['date_from']} "
                  f"{tr['to']} {report_data['date_to']}", fmt_info)
        row += 2

        headers = [
            tr['name'], tr['type'], tr['target'],
            tr['invoice_amount'], tr['pos_amount'],
            tr['achieved'], tr['ratio'], tr['remaining'],
        ]
        for col, hdr in enumerate(headers):
            ws1.write(row, col, hdr, fmt_header)
        row += 1

        for ln in report_data['summary_lines']:
            ws1.write(row, 0, ln['name'], fmt_cell)
            ws1.write(row, 1, ln['type'], fmt_cell)
            ws1.write(row, 2, ln['target'], fmt_money)
            ws1.write(row, 3, ln['invoice_amount'], fmt_money)
            ws1.write(row, 4, ln['pos_amount'], fmt_money)
            ws1.write(row, 5, ln['achieved'],
                      fmt_money_green if ln['achieved'] >= ln['target']
                      else fmt_money)
            ws1.write(row, 6, ln['ratio'] / 100, fmt_percent)
            ws1.write(row, 7, ln['remaining'],
                      fmt_money_red if ln['remaining'] > 0
                      else fmt_money)
            row += 1

        row += 1
        totals = report_data['totals']
        ws1.merge_range(row, 0, row, 1, tr['totals'], fmt_total_label)
        ws1.write(row, 2, totals['target'], fmt_total)
        ws1.write(row, 3, totals['invoice_amount'], fmt_total)
        ws1.write(row, 4, totals['pos_amount'], fmt_total)
        ws1.write(row, 5, totals['achieved'], fmt_total_green)
        ws1.write(row, 6, totals['ratio'] / 100, fmt_percent)
        ws1.write(row, 7, totals['remaining'], fmt_total)

        # ═══════════ DETAIL SHEET ═══════════
        ws2 = workbook.add_worksheet(tr['detail_sheet'][:31])
        if is_rtl:
            ws2.right_to_left()

        d_widths = [22, 14, 20, 22, 12, 16]
        for i, w in enumerate(d_widths):
            ws2.set_column(i, i, w)
        d_last = len(d_widths) - 1

        row = 0
        ws2.merge_range(row, 0, row, d_last,
                        tr['report_title'], fmt_title)
        row += 2

        d_headers = [
            tr['name'], tr['source'], tr['reference'],
            tr['customer'], tr['date'], tr['amount'],
        ]
        for col, hdr in enumerate(d_headers):
            ws2.write(row, col, hdr, fmt_header)
        row += 1

        for ln in report_data['detail_lines']:
            ws2.write(row, 0, ln['name'], fmt_cell)
            ws2.write(row, 1, ln['source'], fmt_cell)
            ws2.write(row, 2, ln['reference'], fmt_cell)
            ws2.write(row, 3, ln['customer'], fmt_cell)
            ws2.write(row, 4, ln['date'], fmt_cell)
            ws2.write(row, 5, ln['amount'],
                      fmt_money_red if ln['amount'] < 0 else fmt_money)
            row += 1

        workbook.close()
        output.seek(0)

        file_data = base64.b64encode(output.read())
        filename = (f"sales_target_report_"
                    f"{self.date_from}_{self.date_to}.xlsx")

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_data,
            'mimetype': ('application/vnd.openxmlformats-'
                         'officedocument.spreadsheetml.sheet'),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
