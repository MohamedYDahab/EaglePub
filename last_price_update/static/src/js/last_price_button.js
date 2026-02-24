/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { Component } from "@odoo/owl";

export class LastPriceButton extends Component {
    static template = "last_price_update.LastPriceButton";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
    }

    get currentOrder() {
        return this.pos.get_order();
    }

    get hasPartner() {
        const order = this.currentOrder;
        return order && order.get_partner();
    }

    async click() {
        const order = this.currentOrder;
        if (!order) return;

        const partner = order.get_partner();
        if (!partner) {
            await this.popup.add(ErrorPopup, {
                title: "No Customer / لا يوجد عميل",
                body: "Please select a customer first.\nيرجى اختيار العميل أولاً",
            });
            return;
        }

        const orderlines = order.get_orderlines();
        if (!orderlines.length) return;

        // Collect unique product IDs
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
                    // Prevent pricelist from overriding on qty change
                    line.price_type = "manual";
                    updated++;
                }
            }

            if (updated === 0) {
                await this.popup.add(ErrorPopup, {
                    title: "No History / لا يوجد سجل",
                    body: "No previous prices found for this customer.\nلم يتم العثور على أسعار سابقة لهذا العميل",
                });
            }
        } catch (error) {
            console.error("Error fetching last prices:", error);
        }
    }
}

ProductScreen.addControlButton({
    component: LastPriceButton,
});
