/** @odoo-module */

import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";

patch(PosOrderline.prototype, {
    canBeMergedWith(orderline) {
        const thisPkgId = this.packaging_id?.id || this.packaging_id || false;
        const otherPkgId = orderline.packaging_id?.id || orderline.packaging_id || false;
        if (thisPkgId !== otherPkgId) {
            return false;
        }
        return super.canBeMergedWith(orderline);
    },
});
