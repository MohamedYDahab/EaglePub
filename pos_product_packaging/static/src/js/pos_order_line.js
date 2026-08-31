/** @odoo-module */

import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";

const packagingId = (line) => line.packaging_id?.id || line.packaging_id || false;

patch(PosOrderline.prototype, {
    /**
     * Two packagings of the same product are two different things to sell.
     *
     * Core compares product, note, discount, price type and price - never
     * packaging - so a 10 kg bag and a 25 kg bag of the same product at the
     * same unit price collapsed into a single line, and the packaging recorded
     * on it was whichever one happened to be added last.
     */
    canBeMergedWith(orderline) {
        if (packagingId(this) !== packagingId(orderline)) {
            return false;
        }
        return super.canBeMergedWith(orderline);
    },

    /**
     * Core's merge() adds up qty and nothing else, so the package count has to
     * be carried over here. Without this, adding 2 bags and then 3 more bags
     * leaves a line reading "3 x Bag" against a quantity of five bags' worth -
     * the quantity is right and the number the cashier reads is wrong.
     */
    merge(orderline) {
        const incoming = orderline.package_qty || 0;
        super.merge(orderline);
        if (incoming) {
            this.package_qty = (this.package_qty || 0) + incoming;
        }
    },
});
