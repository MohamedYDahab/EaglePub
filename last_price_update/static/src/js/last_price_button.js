/** @odoo-module */

import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";

patch(ControlButtons.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },

    get hasPartnerForLastPrice() {
        try {
            const order = this.pos.selectedOrder || this.pos.currentOrder;
            if (!order) return false;
            return !!(order.partner_id || order.partner);
        } catch (e) {
            return false;
        }
    },

    async clickLastPrice() {
        // Access the current order using Odoo 19 API
        const order = this.pos.selectedOrder || this.pos.currentOrder;
        if (!order) return;

        // Access partner using Odoo 19 property access
        const partner = order.partner_id || order.partner;
        if (!partner) {
            this.dialog.add(ConfirmationDialog, {
                title: _t("No Customer / لا يوجد عميل"),
                body: _t("Please select a customer first.\nيرجى اختيار العميل أولاً"),
                confirmLabel: _t("OK"),
            });
            return;
        }

        // Access order lines using Odoo 19 property access
        const orderlines = order.lines || order.orderlines || [];
        if (!orderlines.length) return;

        const productIds = [
            ...new Set(orderlines.map((l) => {
                const product = l.product_id || l.product;
                return product.id;
            })),
        ];

        try {
            const prices = await this.orm.call(
                "pos.session",
                "get_last_customer_prices",
                [partner.id, productIds]
            );

            let updated = 0;
            for (const line of orderlines) {
                const product = line.product_id || line.product;
                const pid = product.id;
                if (prices[pid] !== undefined && prices[pid] !== null) {
                    // Try the Odoo 19 way first, fall back to legacy
                    if (typeof line.set_unit_price === 'function') {
                        line.set_unit_price(prices[pid]);
                    } else {
                        line.price_unit = prices[pid];
                    }
                    line.price_type = "manual";
                    updated++;
                }
            }

            if (updated === 0) {
                this.dialog.add(ConfirmationDialog, {
                    title: _t("No History / لا يوجد سجل"),
                    body: _t("No previous prices found for this customer.\nلم يتم العثور على أسعار سابقة لهذا العميل"),
                    confirmLabel: _t("OK"),
                });
            }
        } catch (error) {
            console.error("Error fetching last prices:", error);
        }
    },
});
