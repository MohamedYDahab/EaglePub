/** @odoo-module */

import { Orderline } from "@point_of_sale/app/components/orderline/orderline";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    get lineScreenValues() {
        const vals = super.lineScreenValues;
        const line = this.line;
        if (vals?.isReceipt && line?.packaging_id) {
            const pkgName =
                line.packaging_id.name ||
                line.packaging_id.display_name;
            if (pkgName) {
                vals.name = `${vals.name} (${pkgName})`;
            }
        }
        return vals;
    },
});
