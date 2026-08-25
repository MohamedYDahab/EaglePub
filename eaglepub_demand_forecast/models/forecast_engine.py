import logging
from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, models

_logger = logging.getLogger(__name__)

# Below this many months of history, a forecast is arithmetic rather than
# evidence. It is still produced - a buyer would rather have a number and a
# warning than a blank - but it is labelled thin.
THIN_HISTORY_MONTHS = 3

# A seasonal index needs at least two observations of the same month to mean
# anything. One December tells you about one December.
MIN_SEASONS = 2


class EaglepubDemandForecastEngine(models.AbstractModel):
    """Turns sales history into a forecast.

    Deliberately kept as plain arithmetic on a monthly series. Every number a
    buyer sees can be traced back to months they can recognise, which is what
    makes a forecast usable in an argument about a purchase order.
    """

    _name = 'eaglepub.demand.forecast.engine'
    _description = 'Demand Forecasting - engine'

    # ──────────────────────────────────────────────────────────────
    # History
    # ──────────────────────────────────────────────────────────────

    @api.model
    def month_starts(self, end, months):
        """The first day of each of the `months` months ending with `end`'s month."""
        first = date(end.year, end.month, 1)
        return [first - relativedelta(months=i) for i in reversed(range(months))]

    @api.model
    def demand_series(self, products, warehouse, end, months):
        """Monthly demand per product, oldest first.

        Demand is what customers ordered, taken from confirmed sale order lines
        and bucketed by the month the order was confirmed. Deliveries are
        deliberately not used: a line that shipped late still represents demand
        in the month it was asked for, and forecasting against your own
        despatch delays would teach the model your bottlenecks rather than your
        customers' behaviour.
        """
        buckets = self.month_starts(end, months)
        index = {d: i for i, d in enumerate(buckets)}
        start = buckets[0]

        series = {p.id: [0.0] * months for p in products}
        if not products:
            return buckets, series

        domain = [
            ('order_id.state', 'in', ('sale', 'done')),
            ('product_id', 'in', products.ids),
            ('order_id.date_order', '>=', start),
            ('order_id.date_order', '<', buckets[-1] + relativedelta(months=1)),
        ]
        if warehouse:
            domain.append(('order_id.warehouse_id', '=', warehouse.id))

        for line in self.env['sale.order.line'].search(domain):
            if line.display_type:
                continue
            ordered = line.order_id.date_order
            bucket = date(ordered.year, ordered.month, 1)
            position = index.get(bucket)
            if position is None:
                continue
            series[line.product_id.id][position] += line.product_uom_qty

        return buckets, series

    # ──────────────────────────────────────────────────────────────
    # Methods
    # ──────────────────────────────────────────────────────────────

    @api.model
    def forecast(self, values, method='smoothing', alpha=0.4):
        """One period ahead from a monthly series.

        Returns 0.0 for an empty series rather than guessing - a product with no
        history has no forecast, and saying so is more useful than a number
        derived from nothing.
        """
        points = [v for v in values if v is not None]
        if not points:
            return 0.0

        if method == 'average':
            return sum(points) / len(points)

        if method == 'weighted':
            # Linear weights: the oldest month counts once, the newest counts
            # as many times as there are months.
            weights = range(1, len(points) + 1)
            total = sum(w for w in weights)
            return sum(v * w for v, w in zip(points, weights)) / total

        # Exponential smoothing. Seeded with the first observation, which is the
        # conventional choice and keeps a short series from being dominated by
        # an arbitrary starting level.
        level = points[0]
        for value in points[1:]:
            level = alpha * value + (1 - alpha) * level
        return level

    @api.model
    def seasonal_index(self, buckets, values, target_month):
        """How this month usually compares with an average month.

        Returns (factor, seasons_used). A factor of 1.0 means no adjustment,
        either because the month behaves like any other or because there is not
        enough history to claim otherwise.
        """
        by_month = defaultdict(list)
        for bucket, value in zip(buckets, values):
            by_month[bucket.month].append(value)

        observations = by_month.get(target_month, [])
        if len(observations) < MIN_SEASONS:
            return 1.0, len(observations)

        overall = [v for vs in by_month.values() for v in vs]
        mean = sum(overall) / len(overall) if overall else 0.0
        if not mean:
            return 1.0, len(observations)

        month_mean = sum(observations) / len(observations)
        factor = month_mean / mean
        # Clamped: a single freak month should nudge a forecast, not treble it.
        return max(0.25, min(4.0, factor)), len(observations)

    # ──────────────────────────────────────────────────────────────
    # Assessment
    # ──────────────────────────────────────────────────────────────

    @api.model
    def history_quality(self, values):
        """(months_with_demand, is_thin). Months of *demand*, not months elapsed.

        A product stocked for two years that sold in one of them has one month
        of evidence, not twenty-four.
        """
        months = len([v for v in values if v])
        return months, months < THIN_HISTORY_MONTHS
