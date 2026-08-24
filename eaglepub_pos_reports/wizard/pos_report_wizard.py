import base64
import io
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

# Orders that represent a real sale. 'draft' is an unfinished ticket and
# 'cancel' never happened, so neither belongs in a takings report.
SOLD_STATES = ('paid', 'done')


class EaglepubPosReportWizard(models.TransientModel):
    _name = 'eaglepub.pos.report.wizard'
    _description = 'POS Reports'

    date_from = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    config_ids = fields.Many2many(
        comodel_name='pos.config',
        string='Points of Sale',
        help='Leave empty to cover every point of sale.',
    )
    report_type = fields.Selection(
        selection=[
            ('shift', 'Shift / Z-Report'),
            ('cashier', 'Cashier Performance'),
            ('product', 'Product Mix'),
            ('hourly', 'Hourly Sales'),
            ('payment', 'Payment Breakdown'),
        ],
        required=True,
        default='shift',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        required=True,
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wiz in self:
            if wiz.date_from > wiz.date_to:
                raise UserError(_('The start date must come before the end date.'))

    # ──────────────────────────────────────────────────────────────
    # Data gathering
    # ──────────────────────────────────────────────────────────────

    def _order_domain(self):
        self.ensure_one()
        domain = [
            ('date_order', '>=', self.date_from),
            ('date_order', '<=', self.date_to),
            ('state', 'in', SOLD_STATES),
            ('company_id', '=', self.company_id.id),
        ]
        if self.config_ids:
            domain.append(('config_id', 'in', self.config_ids.ids))
        return domain

    def _orders(self):
        # date_order is a Datetime and the filter above is a Date, so Odoo
        # compares against midnight. Widening date_to by a day would double
        # count nothing but would silently include the next day's opening
        # orders, so the range is closed on the server side instead.
        return self.env['pos.order'].search(
            self._order_domain() + [('date_order', '<=', self._end_of_day())],
            order='date_order',
        )

    def _end_of_day(self):
        return fields.Datetime.to_string(
            fields.Datetime.to_datetime(f'{self.date_to} 23:59:59')
        )

    def _local(self, dt):
        """UTC datetime to the reader's timezone.

        An hourly report in UTC is worse than no hourly report: a shop in
        Riyadh would see its evening peak land at lunchtime.
        """
        return fields.Datetime.context_timestamp(self, dt) if dt else False

    def _fmt_dt(self, dt):
        """Local datetime as a display string.

        The PDF takes this rather than formatting in the template: QWeb sits in
        XML, where a doubled %% collapses to one and quietly breaks any format
        string. The spreadsheet keeps the datetime object instead, so Excel can
        sort and filter on it.
        """
        local = self._local(dt)
        return local.strftime('%Y-%m-%d %H:%M') if local else ''

    def _data_shift(self, orders):
        by_session = defaultdict(lambda: {'orders': 0, 'sales': 0.0, 'tax': 0.0})
        for order in orders:
            bucket = by_session[order.session_id]
            bucket['orders'] += 1
            bucket['sales'] += order.amount_total
            bucket['tax'] += order.amount_tax
        rows = []
        for session, vals in by_session.items():
            rows.append({
                'session': session.name or '',
                'config': session.config_id.name or '',
                'opened': self._local(session.start_at),
                'closed': self._local(session.stop_at),
                'opened_str': self._fmt_dt(session.start_at),
                'closed_str': self._fmt_dt(session.stop_at),
                'cashier': session.user_id.name or '',
                'orders': vals['orders'],
                'sales': vals['sales'],
                'tax': vals['tax'],
                'average': vals['sales'] / vals['orders'] if vals['orders'] else 0.0,
            })
        return sorted(rows, key=lambda r: (r['config'], r['session']))

    def _data_cashier(self, orders):
        by_user = defaultdict(lambda: {'orders': 0, 'sales': 0.0, 'tax': 0.0, 'discount': 0.0})
        for order in orders:
            bucket = by_user[order.user_id]
            bucket['orders'] += 1
            bucket['sales'] += order.amount_total
            bucket['tax'] += order.amount_tax
            for line in order.lines:
                if line.discount:
                    # What the discount actually gave away, not the percentage.
                    gross = line.price_unit * line.qty
                    bucket['discount'] += gross * (line.discount / 100.0)
        total = sum(v['sales'] for v in by_user.values())
        rows = []
        for user, vals in by_user.items():
            rows.append({
                'cashier': user.name or _('Unassigned'),
                'orders': vals['orders'],
                'sales': vals['sales'],
                'tax': vals['tax'],
                'discount': vals['discount'],
                'average': vals['sales'] / vals['orders'] if vals['orders'] else 0.0,
                'share': vals['sales'] / total if total else 0.0,
            })
        return sorted(rows, key=lambda r: r['sales'], reverse=True)

    def _data_product(self, orders):
        by_product = defaultdict(lambda: {'qty': 0.0, 'sales': 0.0, 'orders': set()})
        for order in orders:
            for line in order.lines:
                bucket = by_product[line.product_id]
                bucket['qty'] += line.qty
                bucket['sales'] += line.price_subtotal_incl
                bucket['orders'].add(order.id)
        total = sum(v['sales'] for v in by_product.values())
        rows = []
        for product, vals in by_product.items():
            rows.append({
                'product': product.display_name or '',
                'code': product.default_code or '',
                'qty': vals['qty'],
                'sales': vals['sales'],
                'orders': len(vals['orders']),
                'share': vals['sales'] / total if total else 0.0,
            })
        return sorted(rows, key=lambda r: r['sales'], reverse=True)

    def _data_hourly(self, orders):
        by_hour = defaultdict(lambda: {'orders': 0, 'sales': 0.0})
        for order in orders:
            local = self._local(order.date_order)
            bucket = by_hour[local.hour if local else 0]
            bucket['orders'] += 1
            bucket['sales'] += order.amount_total
        rows = []
        for hour in range(24):
            vals = by_hour.get(hour)
            if not vals:
                continue
            rows.append({
                'hour': '%02d:00 - %02d:59' % (hour, hour),
                'hour_num': hour,
                'orders': vals['orders'],
                'sales': vals['sales'],
                'average': vals['sales'] / vals['orders'] if vals['orders'] else 0.0,
            })
        return rows

    def _data_payment(self, orders):
        payments = self.env['pos.payment'].search([('pos_order_id', 'in', orders.ids)])
        by_method = defaultdict(lambda: {'count': 0, 'amount': 0.0})
        for payment in payments:
            bucket = by_method[payment.payment_method_id]
            bucket['count'] += 1
            bucket['amount'] += payment.amount
        total = sum(v['amount'] for v in by_method.values())
        rows = []
        for method, vals in by_method.items():
            rows.append({
                'method': method.name or '',
                'count': vals['count'],
                'amount': vals['amount'],
                'share': vals['amount'] / total if total else 0.0,
            })
        return sorted(rows, key=lambda r: r['amount'], reverse=True)

    def _get_report_data(self):
        self.ensure_one()
        orders = self._orders()
        builder = {
            'shift': self._data_shift,
            'cashier': self._data_cashier,
            'product': self._data_product,
            'hourly': self._data_hourly,
            'payment': self._data_payment,
        }[self.report_type]
        rows = builder(orders)
        return {
            'rows': rows,
            'order_count': len(orders),
            'grand_total': sum(orders.mapped('amount_total')),
            'currency': self.company_id.currency_id,
        }

    # ──────────────────────────────────────────────────────────────
    # Column definitions - shared by the PDF and the spreadsheet
    # ──────────────────────────────────────────────────────────────

    def _columns(self, tr):
        """(key, label, kind, width) per report. kind drives formatting."""
        return {
            'shift': [
                ('session', tr['session'], 'text', 20),
                ('config', tr['point_of_sale'], 'text', 18),
                ('opened', tr['opened'], 'datetime', 18),
                ('closed', tr['closed'], 'datetime', 18),
                ('cashier', tr['cashier'], 'text', 18),
                ('orders', tr['orders'], 'int', 10),
                ('sales', tr['sales'], 'money', 14),
                ('tax', tr['tax'], 'money', 12),
                ('average', tr['average_ticket'], 'money', 14),
            ],
            'cashier': [
                ('cashier', tr['cashier'], 'text', 24),
                ('orders', tr['orders'], 'int', 10),
                ('sales', tr['sales'], 'money', 14),
                ('tax', tr['tax'], 'money', 12),
                ('discount', tr['discount_given'], 'money', 14),
                ('average', tr['average_ticket'], 'money', 14),
                ('share', tr['share'], 'percent', 12),
            ],
            'product': [
                ('code', tr['code'], 'text', 14),
                ('product', tr['product'], 'text', 34),
                ('qty', tr['quantity'], 'float', 12),
                ('sales', tr['sales'], 'money', 14),
                ('orders', tr['orders'], 'int', 10),
                ('share', tr['share'], 'percent', 12),
            ],
            'hourly': [
                ('hour', tr['hour'], 'text', 18),
                ('orders', tr['orders'], 'int', 10),
                ('sales', tr['sales'], 'money', 14),
                ('average', tr['average_ticket'], 'money', 14),
            ],
            'payment': [
                ('method', tr['payment_method'], 'text', 26),
                ('count', tr['count'], 'int', 10),
                ('amount', tr['amount'], 'money', 16),
                ('share', tr['share'], 'percent', 12),
            ],
        }[self.report_type]

    def _totalled_keys(self):
        """Columns that make sense to sum. Averages and shares do not."""
        return {
            'shift': ('orders', 'sales', 'tax'),
            'cashier': ('orders', 'sales', 'tax', 'discount'),
            'product': ('qty', 'sales', 'orders'),
            'hourly': ('orders', 'sales'),
            'payment': ('count', 'amount'),
        }[self.report_type]

    # ──────────────────────────────────────────────────────────────
    # Translations
    # ──────────────────────────────────────────────────────────────

    def _get_translations(self):
        lang = self.env.user.lang or 'en_US'
        if lang.startswith('ar'):
            return {
                'is_rtl': True,
                'titles': {
                    'shift': 'تقرير إغلاق الورديات',
                    'cashier': 'أداء أمناء الصندوق',
                    'product': 'حركة المنتجات',
                    'hourly': 'المبيعات بالساعة',
                    'payment': 'توزيع طرق الدفع',
                },
                'company': 'الشركة', 'period': 'الفترة', 'to': 'إلى',
                'point_of_sale': 'نقطة البيع', 'session': 'الوردية',
                'opened': 'وقت الفتح', 'closed': 'وقت الإغلاق',
                'cashier': 'أمين الصندوق', 'orders': 'عدد الطلبات',
                'sales': 'المبيعات', 'tax': 'الضريبة',
                'average_ticket': 'متوسط الفاتورة', 'discount_given': 'الخصم الممنوح',
                'share': 'النسبة', 'product': 'المنتج', 'code': 'الرمز',
                'quantity': 'الكمية', 'hour': 'الساعة',
                'payment_method': 'طريقة الدفع', 'count': 'العدد',
                'amount': 'المبلغ', 'totals': 'الإجمالي',
                'no_data': 'لا توجد بيانات في هذه الفترة',
            }
        return {
            'is_rtl': False,
            'titles': {
                'shift': 'Shift / Z-Report',
                'cashier': 'Cashier Performance',
                'product': 'Product Mix',
                'hourly': 'Hourly Sales',
                'payment': 'Payment Breakdown',
            },
            'company': 'Company', 'period': 'Period', 'to': 'to',
            'point_of_sale': 'Point of Sale', 'session': 'Session',
            'opened': 'Opened', 'closed': 'Closed',
            'cashier': 'Cashier', 'orders': 'Orders',
            'sales': 'Sales', 'tax': 'Tax',
            'average_ticket': 'Average Ticket', 'discount_given': 'Discount Given',
            'share': 'Share', 'product': 'Product', 'code': 'Code',
            'quantity': 'Quantity', 'hour': 'Hour',
            'payment_method': 'Payment Method', 'count': 'Count',
            'amount': 'Amount', 'totals': 'Totals',
            'no_data': 'Nothing was sold in this period',
        }

    # ──────────────────────────────────────────────────────────────
    # Output
    # ──────────────────────────────────────────────────────────────

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'eaglepub_pos_reports.action_report_eaglepub_pos'
        ).report_action(self)

    def action_export_excel(self):
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(_(
                'The xlsxwriter Python library is not installed, so Excel export '
                'is unavailable. PDF export still works.'
            ))

        tr = self._get_translations()
        rtl = tr['is_rtl']
        data = self._get_report_data()
        columns = self._columns(tr)

        output = io.BytesIO()
        book = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = book.add_worksheet(tr['titles'][self.report_type][:31])
        if rtl:
            sheet.right_to_left()

        text_align = 'right' if rtl else 'left'
        num_align = 'left' if rtl else 'right'

        f_title = book.add_format({'bold': True, 'font_size': 16, 'align': 'center',
                                   'valign': 'vcenter', 'font_color': '#3B2436'})
        f_info = book.add_format({'font_size': 10, 'italic': True, 'align': text_align})
        f_head = book.add_format({'bold': True, 'font_size': 10, 'align': 'center',
                                  'valign': 'vcenter', 'bg_color': '#714B67',
                                  'font_color': 'white', 'border': 1, 'text_wrap': True})
        f_text = book.add_format({'font_size': 10, 'border': 1, 'align': text_align})
        f_int = book.add_format({'font_size': 10, 'border': 1, 'align': 'center'})
        f_float = book.add_format({'font_size': 10, 'border': 1, 'num_format': '#,##0.###',
                                   'align': num_align})
        f_money = book.add_format({'font_size': 10, 'border': 1, 'num_format': '#,##0.00',
                                   'align': num_align})
        f_pct = book.add_format({'font_size': 10, 'border': 1, 'num_format': '0.0%',
                                 'align': 'center'})
        f_dt = book.add_format({'font_size': 10, 'border': 1, 'align': 'center',
                                'num_format': 'yyyy-mm-dd hh:mm'})
        f_tot_lbl = book.add_format({'bold': True, 'font_size': 11, 'border': 1,
                                     'bg_color': '#F3EBF1', 'align': text_align})
        f_tot = book.add_format({'bold': True, 'font_size': 11, 'border': 1,
                                 'num_format': '#,##0.00', 'bg_color': '#F3EBF1',
                                 'align': num_align})

        last = len(columns) - 1
        sheet.merge_range(0, 0, 0, last, tr['titles'][self.report_type], f_title)
        sheet.write(1, 0, '%s: %s' % (tr['company'], self.company_id.name), f_info)
        sheet.write(2, 0, '%s: %s %s %s' % (tr['period'], self.date_from, tr['to'], self.date_to), f_info)
        if self.config_ids:
            sheet.write(3, 0, '%s: %s' % (tr['point_of_sale'],
                                          ', '.join(self.config_ids.mapped('name'))), f_info)

        row = 5
        for col, (_key, label, _kind, width) in enumerate(columns):
            sheet.write(row, col, label, f_head)
            sheet.set_column(col, col, width)
        sheet.freeze_panes(row + 1, 0)

        fmt_for = {'text': f_text, 'int': f_int, 'float': f_float,
                   'money': f_money, 'percent': f_pct, 'datetime': f_dt}

        row += 1
        if not data['rows']:
            sheet.merge_range(row, 0, row, last, tr['no_data'], f_text)
        else:
            for line in data['rows']:
                for col, (key, _label, kind, _w) in enumerate(columns):
                    value = line.get(key)
                    if kind == 'datetime':
                        # xlsxwriter cannot store a tz-aware datetime.
                        value = value.replace(tzinfo=None) if value else ''
                        sheet.write_datetime(row, col, value, f_dt) if value else \
                            sheet.write(row, col, '', f_dt)
                    else:
                        sheet.write(row, col, value if value is not None else '', fmt_for[kind])
                row += 1

            totals = self._totalled_keys()
            sheet.write(row, 0, tr['totals'], f_tot_lbl)
            for col, (key, _label, kind, _w) in enumerate(columns):
                if col == 0:
                    continue
                if key in totals:
                    sheet.write(row, col, sum(l.get(key) or 0 for l in data['rows']), f_tot)
                else:
                    sheet.write(row, col, '', f_tot_lbl)

        book.close()
        output.seek(0)

        filename = 'pos_%s_%s_%s.xlsx' % (self.report_type, self.date_from, self.date_to)
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
