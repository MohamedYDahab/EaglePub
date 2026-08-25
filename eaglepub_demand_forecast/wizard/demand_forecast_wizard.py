import json
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# A rule is only worth querying when it is off by more than this share of the
# forecast. Reporting every rounding difference would train people to ignore
# the column.
RULE_TOLERANCE = 0.25


class EaglepubDemandForecastWizard(models.TransientModel):
    _name = 'eaglepub.demand.forecast.wizard'
    _description = 'Run a Demand Forecast'

    warehouse_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string='Warehouse',
        help='Leave empty to forecast across every warehouse together.',
    )
    date_to = fields.Date(
        string='History Up To',
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    months = fields.Integer(
        string='Months of History', default=24, required=True,
        help='Defaults to 24 because seasonality needs the same calendar month '
             'at least twice. At 12 months every month appears once and no '
             'seasonal adjustment is possible.',
    )
    method = fields.Selection(
        selection=[
            ('average', 'Average'),
            ('weighted', 'Weighted average'),
            ('smoothing', 'Exponential smoothing'),
        ],
        default='smoothing', required=True,
    )
    alpha = fields.Float(string='Smoothing Factor', default=0.4)
    use_seasonality = fields.Boolean(string='Apply Seasonality', default=True)

    product_ids = fields.Many2many(
        comodel_name='product.product',
        string='Products',
        help='Leave empty to cover every storable product that sold in the period.',
    )
    categ_ids = fields.Many2many(
        comodel_name='product.category',
        string='Product Categories',
        help='Narrow to particular categories.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company, required=True,
    )

    @api.constrains('months', 'alpha')
    def _check_params(self):
        for wiz in self:
            if not 2 <= wiz.months <= 60:
                raise UserError(_('Use between 2 and 60 months of history.'))
            if not 0 < wiz.alpha <= 1:
                raise UserError(_(
                    'The smoothing factor must be greater than 0 and at most 1.'))

    # ──────────────────────────────────────────────────────────────

    def _products(self):
        """What to forecast.

        Defaults to storable products that actually sold in the period, rather
        than the whole catalogue - a forecast of zero for nine hundred products
        nobody ordered is noise that hides the hundred that matter.
        """
        self.ensure_one()
        if self.product_ids:
            return self.product_ids

        domain = [('is_storable', '=', True)]
        if self.categ_ids:
            domain.append(('categ_id', 'child_of', self.categ_ids.ids))

        engine = self.env['eaglepub.demand.forecast.engine']
        buckets = engine.month_starts(self.date_to, self.months)
        line_domain = [
            ('order_id.state', 'in', ('sale', 'done')),
            ('order_id.date_order', '>=', buckets[0]),
            ('order_id.date_order', '<', buckets[-1] + relativedelta(months=1)),
        ]
        if self.warehouse_id:
            line_domain.append(('order_id.warehouse_id', '=', self.warehouse_id.id))

        sold = self.env['sale.order.line'].search(line_domain).mapped('product_id')
        return sold.filtered_domain(domain)

    def action_forecast(self):
        self.ensure_one()
        products = self._products()
        if not products:
            raise UserError(_(
                'Nothing sold in this period, so there is nothing to forecast. '
                'Widen the history or pick products explicitly.'))

        engine = self.env['eaglepub.demand.forecast.engine']
        buckets, series = engine.demand_series(
            products, self.warehouse_id, self.date_to, self.months)
        target_month = (buckets[-1] + relativedelta(months=1)).month

        forecast = self.env['eaglepub.demand.forecast'].create({
            'warehouse_id': self.warehouse_id.id,
            'date_to': self.date_to,
            'months': self.months,
            'method': self.method,
            'alpha': self.alpha,
            'use_seasonality': self.use_seasonality,
            'company_id': self.company_id.id,
        })

        orderpoints = self._orderpoints(products)
        lines = []
        for product in products:
            values = series.get(product.id) or []
            base = engine.forecast(values, method=self.method, alpha=self.alpha)
            months_with_demand, thin = engine.history_quality(values)

            # Seasonality is withheld from thin history on purpose. A product
            # with two months of sales has two observations of every month,
            # both of them usually zero, and the index that comes out of that
            # is noise wearing a decimal point.
            factor = 1.0
            if self.use_seasonality and not thin:
                factor, _seasons = engine.seasonal_index(
                    buckets, values, target_month)

            expected = base * factor
            orderpoint = orderpoints.get(product.id)
            disagrees, note = self._compare_rule(orderpoint, expected, thin)

            lines.append((0, 0, {
                'product_id': product.id,
                'forecast_qty': expected,
                'base_qty': base,
                'seasonal_factor': factor,
                'history_json': json.dumps([round(v, 2) for v in values]),
                'history_months': months_with_demand,
                'history_is_thin': thin,
                'qty_available': product.qty_available,
                'orderpoint_id': orderpoint.id if orderpoint else False,
                'orderpoint_min': orderpoint.product_min_qty if orderpoint else 0.0,
                'rule_disagrees': disagrees,
                'rule_note': note,
            }))
        forecast.write({'line_ids': lines})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Demand Forecast'),
            'res_model': 'eaglepub.demand.forecast',
            'res_id': forecast.id,
            'view_mode': 'form',
        }

    def _orderpoints(self, products):
        domain = [('product_id', 'in', products.ids)]
        if self.warehouse_id:
            domain.append(('warehouse_id', '=', self.warehouse_id.id))
        found = {}
        for point in self.env['stock.warehouse.orderpoint'].search(domain):
            found.setdefault(point.product_id.id, point)
        return found

    def _compare_rule(self, orderpoint, expected, thin):
        """Does the existing reordering rule agree with the forecast?

        Only reports where a person would actually want to look: no rule for a
        product with real demand, or a minimum far enough from a month of
        expected demand to matter. Thin history never triggers a query, because
        arguing with somebody's reordering rule on two months of data is how a
        report loses its credibility.
        """
        if thin:
            return False, ''

        if not orderpoint:
            if expected > 0:
                return True, _(
                    'No reordering rule, but %(qty).2f is expected next month.',
                    qty=expected)
            return False, ''

        minimum = orderpoint.product_min_qty
        if expected <= 0:
            return False, ''

        gap = minimum - expected
        if abs(gap) <= expected * RULE_TOLERANCE:
            return False, ''

        if gap < 0:
            return True, _(
                'Minimum is %(min).2f but %(qty).2f is expected next month - '
                'this may run out.', min=minimum, qty=expected)
        return True, _(
            'Minimum is %(min).2f against expected demand of %(qty).2f - '
            'this may be holding stock you do not need.',
            min=minimum, qty=expected)
