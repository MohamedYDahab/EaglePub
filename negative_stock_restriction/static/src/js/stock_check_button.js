/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(ControlButtons.prototype, {
    setup() {
        super.setup(...arguments);
        this._stockCheckOrm = useService("orm");
        this._stockCheckDialog = useService("dialog");
    },

    async onClickStockCheck() {
        const order = this.pos.get_order();
        if (!order) return;

        const orderlines = order.get_orderlines();
        if (!orderlines.length) return;

        const productIds = [
            ...new Set(orderlines.map((l) => l.get_product().id)),
        ];

        try {
            const result = await this._stockCheckOrm.call(
                "pos.session",
                "get_stock_for_products",
                [productIds]
            );

            if (!result.enabled) {
                this._stockCheckDialog.add(AlertDialog, {
                    title: _t("Stock Check"),
                    body: _t("Stock restriction is disabled."),
                });
                return;
            }

            const stock = result.stock;
            const exempt = result.exempt || {};
            const threshold = result.threshold || 0;
            const lines_info = [];

            for (const line of orderlines) {
                const pid = line.get_product().id;
                const available = stock[pid];
                if (available === undefined || available === null) continue;

                const qty = line.get_quantity();
                const isExempt = exempt[pid] || false;
                let icon = "";

                if (isExempt) {
                    icon = " 🔓"; // exempt
                } else if (available >= qty && available > threshold) {
                    icon = " ✅";
                } else if (available >= qty) {
                    icon = " ⚠️"; // low stock
                } else {
                    icon = " ❌"; // insufficient
                }

                lines_info.push(
                    line.get_product().display_name + ": " +
                    _t("Available") + " " + parseFloat(available).toFixed(1) + ", " +
                    _t("Ordered") + " " + qty +
                    (isExempt ? " (" + _t("Exempt") + ")" : "") +
                    icon
                );
            }

            if (lines_info.length > 0) {
                const hasIssue = orderlines.some((line) => {
                    const pid = line.get_product().id;
                    const avail = stock[pid];
                    const isExempt = exempt[pid] || false;
                    return !isExempt && avail !== undefined &&
                           avail < line.get_quantity();
                });
                this._stockCheckDialog.add(AlertDialog, {
                    title: hasIssue
                        ? _t("Insufficient Stock ⚠️")
                        : _t("Stock OK ✅"),
                    body: lines_info.join("\n"),
                });
            }
        } catch (error) {
            console.error("Stock check error:", error);
        }
    },
});
