/** @odoo-module */

import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";

patch(ControlButtons.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },

    get hasPartnerForLastPrice() {
        const order = this.pos.get_order();
        return order && order.get_partner();
    },

    async clickLastPrice() {
        const order = this.pos.get_order();
        if (!order) return;

        const partner = order.get_partner();
        if (!partner) {
            this.dialog.add(AlertDialog, {
                title: "No Customer / لا يوجد عميل",
                body: "Please select a customer first.\nيرجى اختيار العميل أولاً",
            });
            return;
        }

        const orderlines = order.get_orderlines();
        if (!orderlines.length) return;

        const productIds = [
            ...new Set(orderlines.map((l) => l.get_product().id)),
        ];

        try {
            const prices = await this.orm.call(
                "pos.session",
                "get_last_customer_prices",
                [partner.id, productIds]
            );

            let updated = 0;
            for (const line of orderlines) {
                const pid = line.get_product().id;
                if (prices[pid] !== undefined && prices[pid] !== null) {
                    line.set_unit_price(prices[pid]);
                    line.price_type = "manual";
                    updated++;
                }
            }

            if (updated === 0) {
                this.dialog.add(AlertDialog, {
                    title: "No History / لا يوجد سجل",
                    body: "No previous prices found for this customer.\nلم يتم العثور على أسعار سابقة لهذا العميل",
                });
            }
        } catch (error) {
            console.error("Error fetching last prices:", error);
        }
    },
});