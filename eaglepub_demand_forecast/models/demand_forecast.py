import json
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EaglepubDemandForecast(models.Model):
    _name = 'eaglepub.demand.forecast'
    _description = 'Demand Forecast'
    _order = 'create_date desc, id desc'
    _rec_name = 'display_name'

    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string='Warehouse',
        help='Leave empty to forecast across every warehouse together.',
    )
    date_to = fields.Date(
        string='History Up To',
        required=True,
        help='The last month included in the history. The forecast is for the '
             'month after this one.',
    )
    months = fields.Integer(
        string='Months of History',
        default=24,
        required=True,
        help='Seasonality needs the same calendar month at least twice, so a '
             'period shorter than 13 months can never produce one.',
    )
    method = fields.Selection(
        selection=[
            ('average', 'Average'),
            ('weighted', 'Weighted average'),
            ('smoothing', 'Exponential smoothing'),
        ],
        default='smoothing',
        required=True,
    )
    alpha = fields.Float(
        string='Smoothing Factor',
        default=0.4,
        help='How heavily the most recent month counts, between 0 and 1. '
             'Higher reacts faster and is noisier.',
    )
    use_seasonality = fields.Boolean(
        string='Apply Seasonality',
        default=True,
        help='Adjust for how this month usually compares with an average month. '
             'Needs at least two previous years of the same month, and is never '
             'applied to a product with thin history.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company,
        required=True,
    )

    line_ids = fields.One2many(
        comodel_name='eaglepub.demand.forecast.line',
        inverse_name='forecast_id',
        string='Products',
    )
    line_count = fields.Integer(compute='_compute_counts', store=True)
    disagreement_count = fields.Integer(
        compute='_compute_counts', store=True,
        string='Rules to Review',
    )
    thin_count = fields.Integer(
        compute='_compute_counts', store=True,
        string='Thin History',
    )
    display_name = fields.Char(compute='_compute_display_name', store=True)
    warehouse_label = fields.Char(
        string='Warehouse Covered', compute='_compute_warehouse_label',
        help='Reads "All warehouses" when no single warehouse was chosen, so an '
             'empty cell is never mistaken for missing data.',
    )

    _alpha_range = models.Constraint(
        'CHECK(alpha > 0 AND alpha <= 1)',
        'The smoothing factor must be greater than 0 and at most 1.',
    )
    _months_range = models.Constraint(
        'CHECK(months >= 2 AND months <= 60)',
        'Use between 2 and 60 months of history.',
    )

    @api.depends('line_ids', 'line_ids.rule_disagrees', 'line_ids.history_is_thin')
    def _compute_counts(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.disagreement_count = len(rec.line_ids.filtered('rule_disagrees'))
            rec.thin_count = len(rec.line_ids.filtered('history_is_thin'))

    @api.depends('warehouse_id')
    def _compute_warehouse_label(self):
        for rec in self:
            rec.warehouse_label = rec.warehouse_id.name or _('All warehouses')

    @api.depends('warehouse_id', 'date_to', 'method')
    def _compute_display_name(self):
        labels = dict(self._fields['method'].selection)
        for rec in self:
            rec.display_name = '%s - %s (%s)' % (
                rec.warehouse_id.name or _('All warehouses'),
                rec.date_to or '', labels.get(rec.method, ''))

    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Forecast'),
            'res_model': 'eaglepub.demand.forecast.line',
            'view_mode': 'list,form',
            'domain': [('forecast_id', '=', self.id)],
        }


class EaglepubDemandForecastLine(models.Model):
    _name = 'eaglepub.demand.forecast.line'
    _description = 'Demand Forecast Line'
    _order = 'forecast_qty desc, id'

    forecast_id = fields.Many2one(
        comodel_name='eaglepub.demand.forecast',
        string='Forecast Run',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one('product.product', string='Product', required=True)
    uom_name = fields.Char(related='product_id.uom_id.name', string='Unit')

    # ── the forecast ──
    forecast_qty = fields.Float(
        string='Forecast',
        digits='Product Unit of Measure',
        help='Expected demand for the month after the history period.',
    )
    base_qty = fields.Float(
        string='Before Seasonality',
        digits='Product Unit of Measure',
        help='The forecast before any seasonal adjustment.',
    )
    seasonal_factor = fields.Float(
        string='Seasonal Factor',
        default=1.0,
        help='How this month usually compares with an average month. '
             '1.00 means no adjustment was made.',
    )

    # ── the working ──
    history_json = fields.Char(
        string='Monthly Demand',
        help='The months behind this forecast, oldest first.',
    )
    history_months = fields.Integer(
        string='Months With Demand',
        help='How many months actually had sales. This is the evidence behind '
             'the forecast, not the length of the period.',
    )
    history_is_thin = fields.Boolean(
        string='Thin History',
        help='Too few months of demand to place much weight on the number.',
    )

    # ── against reality ──
    qty_available = fields.Float(
        string='On Hand', digits='Product Unit of Measure')
    orderpoint_id = fields.Many2one(
        'stock.warehouse.orderpoint', string='Reordering Rule')
    orderpoint_min = fields.Float(
        string='Rule Minimum', digits='Product Unit of Measure')
    rule_disagrees = fields.Boolean(string='Review Rule')
    rule_note = fields.Char(string='Why')

    def action_open_orderpoint(self):
        self.ensure_one()
        if not self.orderpoint_id:
            raise UserError(_('This product has no reordering rule.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.warehouse.orderpoint',
            'res_id': self.orderpoint_id.id,
            'view_mode': 'form',
        }

    history_display = fields.Char(
        string='History',
        compute='_compute_history_display',
        help='Demand month by month, oldest first. This is the evidence the '
             'forecast was built from.',
    )

    @api.depends('history_json', 'forecast_id.date_to', 'forecast_id.months')
    def _compute_history_display(self):
        """Pair the stored series back up with the months it came from.

        The months are recomputed rather than stored per line, because they are
        the same for every line of a forecast and storing them once per product
        would multiply the same twelve dates across the whole catalogue.
        """
        for line in self:
            try:
                values = json.loads(line.history_json or '[]')
            except ValueError:
                values = []
            forecast = line.forecast_id
            if not values or not forecast.date_to:
                line.history_display = ''
                continue
            last = forecast.date_to.replace(day=1)
            months = [
                last - relativedelta(months=i)
                for i in reversed(range(len(values)))
            ]
            line.history_display = '  |  '.join(
                '%s %s' % (m.strftime('%b %y'), ('%g' % v))
                for m, v in zip(months, values)
            )
