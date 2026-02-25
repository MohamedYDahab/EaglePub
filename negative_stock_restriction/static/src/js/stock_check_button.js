/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

export class StockCheckButton extends Component {
    static template = "negative_stock_restriction.StockCheckButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
    }

    async click() {
        const order = this.pos.get_order();
        if (!order) return;

        const orderlines = order.get_orderlines();
        if (!orderlines.length) return;

        const productIds = [
            ...new Set(orderlines.map((l) => l.get_product().id)),
        ];

        try {
            const result = await this.orm.call(
                "pos.session",
                "get_stock_for_products",
                [productIds]
            );

            if (!result.enabled) {
                await this.popup.add(ErrorPopup, {
                    title: _t("Stock Check"),
                    body: _t("Stock restriction is disabled.") +
                          "\n" + "تقييد المخزون معطل",
                });
                return;
            }

            const stock = result.stock;
            const lines_info = [];

            for (const line of orderlines) {
                const pid = line.get_product().id;
                const available = stock[pid];
                if (available === undefined || available === null) continue;
                const ok = available >= line.get_quantity();
                lines_info.push(
                    line.get_product().display_name + ": " +
                    _t("Available") + " " + available + ", " +
                    _t("Ordered") + " " + line.get_quantity() +
                    (ok ? " ✅" : " ⚠️")
                );
            }

            if (lines_info.length > 0) {
                const hasIssue = orderlines.some((line) => {
                    const avail = stock[line.get_product().id];
                    return avail !== undefined && avail < line.get_quantity();
                });
                await this.popup.add(ErrorPopup, {
                    title: hasIssue ? _t("Insufficient Stock ⚠️") : _t("Stock OK ✅"),
                    body: lines_info.join("\n"),
                });
            }
        } catch (error) {
            console.error("Stock check error:", error);
        }
    }
}

ProductScreen.addControlButton({
    component: StockCheckButton,
    condition: function () {
        return true;
    },
});
