/** @odoo-module */

import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Orderline.prototype, {
    setup(options) {
        super.setup(...arguments);
        this.packaging_id = options.packaging_id || false;
        this.package_qty = options.package_qty || 0;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.packaging_id = json.packaging_id || false;
        this.package_qty = json.package_qty || 0;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.packaging_id = this.packaging_id ? (this.packaging_id.id || this.packaging_id) : false;
        json.package_qty = this.package_qty || 0;
        return json;
    },

    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.packaging_id = this.packaging_id;
        result.package_qty = this.package_qty;
        result.packaging_name = this.packaging_id ? this.packaging_id.name : '';
        return result;
    },

    getDisplayData() {
        const data = super.getDisplayData(...arguments);
        data.packaging_id = this.packaging_id;
        data.package_qty = this.package_qty;
        data.packaging_name = this.packaging_id ? this.packaging_id.name : '';
        return data;
    },
});