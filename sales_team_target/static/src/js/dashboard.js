/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

class SalesTargetDashboard extends Component {
    static template = "sales_team_target.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.barRef = useRef("barChart");
        this.trendRef = useRef("trendChart");
        this.doughnutRef = useRef("doughnutChart");

        this.state = useState({
            data: {},
            loading: true,
            month: String(new Date().getMonth() + 1),
            year: new Date().getFullYear(),
        });

        this.months = [
            {value: "1", label: "January"}, {value: "2", label: "February"},
            {value: "3", label: "March"}, {value: "4", label: "April"},
            {value: "5", label: "May"}, {value: "6", label: "June"},
            {value: "7", label: "July"}, {value: "8", label: "August"},
            {value: "9", label: "September"}, {value: "10", label: "October"},
            {value: "11", label: "November"}, {value: "12", label: "December"},
        ];

        this._barChart = null;
        this._trendChart = null;
        this._doughnutChart = null;
        this._chartsNeedRender = false;

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js");
            await this._fetchData();
        });

        // Render charts after initial mount
        onMounted(() => {
            this._renderCharts();
        });

        // Re-render charts after any OWL patch (state change re-render)
        // This is the KEY fix: when state changes, OWL re-renders the DOM
        // and replaces canvas elements. We must re-binds charts to the new canvas.
        onPatched(() => {
            if (this._chartsNeedRender) {
                this._chartsNeedRender = false;
                this._renderCharts();
            }
        });

        // Clean up chart instances on unmount to prevent memory leaks
        onWillUnmount(() => {
            this._destroyCharts();
        });
    }

    async _fetchData() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "sales.target", "get_dashboard_data",
                [], {month: this.state.month, year: this.state.year}
            );
        } catch (e) {
            console.error("Failed to fetch dashboard data:", e);
            this.state.data = {};
        }
        this.state.loading = false;
        // Flag that charts need rendering after the DOM updates
        this._chartsNeedRender = true;
    }

    async onMonthChange(ev) {
        this.state.month = ev.target.value;
        await this._fetchData();
    }

    async onYearChange(ev) {
        this.state.year = parseInt(ev.target.value);
        await this._fetchData();
    }

    async onRefreshDashboard() {
        await this._fetchData();
    }

    /* ───── Charts ───── */

    _destroyCharts() {
        if (this._barChart) { this._barChart.destroy(); this._barChart = null; }
        if (this._trendChart) { this._trendChart.destroy(); this._trendChart = null; }
        if (this._doughnutChart) { this._doughnutChart.destroy(); this._doughnutChart = null; }
    }

    _renderCharts() {
        // Destroy existing chart instances first to prevent canvas reuse errors
        this._destroyCharts();
        this._renderBarChart();
        this._renderTrendChart();
        this._renderDoughnutChart();
    }

    _renderBarChart() {
        const el = this.barRef.el;
        if (!el || !this.state.data.chart_data) return;

        const d = this.state.data.chart_data;
        if (!d.length) return;

        this._barChart = new Chart(el, {
            type: "bar",
            data: {
                labels: d.map(r => r.name),
                datasets: [
                    {
                        label: "Target",
                        data: d.map(r => r.target),
                        backgroundColor: "#34495e",
                        borderRadius: 4,
                        barPercentage: 0.7,
                    },
                    {
                        label: "Achieved",
                        data: d.map(r => r.achieved),
                        backgroundColor: "#27ae60",
                        borderRadius: 4,
                        barPercentage: 0.7,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {position: "top", labels: {usePointStyle: true}},
                    title: {display: true, text: "Target vs Achieved", font: {size: 15, weight: "600"}},
                },
                scales: {
                    y: {beginAtZero: true, ticks: {callback: v => v.toLocaleString()}, grid: {color: "#f0f0f0"}},
                    x: {grid: {display: false}},
                },
            },
        });
    }

    _renderTrendChart() {
        const el = this.trendRef.el;
        if (!el || !this.state.data.trend_data) return;

        const d = this.state.data.trend_data;
        this._trendChart = new Chart(el, {
            type: "line",
            data: {
                labels: d.map(r => r.month),
                datasets: [
                    {
                        label: "Target",
                        data: d.map(r => r.target),
                        borderColor: "#34495e",
                        backgroundColor: "rgba(52,73,94,0.08)",
                        fill: true, tension: 0.35, pointRadius: 4,
                    },
                    {
                        label: "Achieved",
                        data: d.map(r => r.achieved),
                        borderColor: "#27ae60",
                        backgroundColor: "rgba(39,174,96,0.08)",
                        fill: true, tension: 0.35, pointRadius: 4,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {position: "top", labels: {usePointStyle: true}},
                    title: {display: true, text: "Yearly Trend " + this.state.year, font: {size: 15, weight: "600"}},
                },
                scales: {
                    y: {beginAtZero: true, ticks: {callback: v => v.toLocaleString()}, grid: {color: "#f0f0f0"}},
                    x: {grid: {display: false}},
                },
            },
        });
    }

    _renderDoughnutChart() {
        const el = this.doughnutRef.el;
        if (!el || !this.state.data) return;

        const inv = this.state.data.total_invoice || 0;
        const pos = this.state.data.total_pos || 0;
        if (!inv && !pos) return;

        this._doughnutChart = new Chart(el, {
            type: "doughnut",
            data: {
                labels: ["Invoice Sales", "POS Sales"],
                datasets: [{
                    data: [inv, pos],
                    backgroundColor: ["#3498db", "#e67e22"],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "65%",
                plugins: {
                    legend: {position: "bottom", labels: {usePointStyle: true}},
                    title: {display: true, text: "Sales Breakdown", font: {size: 15, weight: "600"}},
                },
            },
        });
    }

    /* ───── Helpers ───── */

    fmt(val) {
        return (val || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    }

    ratioColor(r) {
        if (r >= 100) return "success";
        if (r >= 50) return "warning";
        return "danger";
    }

    barWidth(r) {
        return Math.min(r, 100);
    }

    onViewAll() {
        this.action.doAction("sales_team_target.action_sales_target_all");
    }

    onClickRow(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sales.target",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("sales_target_dashboard", SalesTargetDashboard);
