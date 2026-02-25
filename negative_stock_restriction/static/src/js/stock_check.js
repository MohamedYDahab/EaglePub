/** @odoo-module */

import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";

patch(ControlButtons.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
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
            const result = await this.orm.call(
                "pos.session",
                "get_stock_for_products",
                [productIds]
            );

            if (!result.enabled) return;

            const stock = result.stock;
            const mode = result.mode;
            const bypass = result.bypass;
            const issues = [];

            for (const line of orderlines) {
                const pid = line.get_product().id;
                const available = stock[pid];
                if (available === undefined || available === null) continue;
                if (available >= line.get_quantity()) continue;
                issues.push(
                    `${line.get_product().display_name}: ` +
                    `Available ${available}, Ordered ${line.get_quantity()}`
                );
            }

            if (issues.length > 0) {
                const msg = _t("Insufficient Stock:") + "\n" + issues.join("\n");
                if (mode === 'hard' && !bypass) {
                    this.dialog.add(AlertDialog, {
                        title: _t("Negative Stock Blocked"),
                        body: msg + "\n\n" +
                              _t("Please adjust quantities or restock.") + "\n" +
                              "يرجى تعديل الكميات أو إعادة التخزين",
                    });
                    return 'blocked';
                } else {
                    this.dialog.add(AlertDialog, {
                        title: _t("Low Stock Warning"),
                        body: msg + "\n\n" +
                              _t("Proceeding with negative stock.") + "\n" +
                              "المتابعة بمخزون سالب",
                    });
                    return 'warned';
                }
            }
            return 'ok';
        } catch (error) {
            console.error("Stock check error:", error);
            return 'error';
        }
    },
});
