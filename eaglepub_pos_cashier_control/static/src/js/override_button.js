/** @odoo-module */

import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(ControlButtons.prototype, {
    get eaglepubShowOverride() {
        return Boolean(this.pos.eaglepubPolicy);
    },

    get eaglepubOverridden() {
        return Boolean(this.pos.getOrder()?.eaglepubOverridden);
    },

    async eaglepubClickOverride() {
        await this.pos.eaglepubRequestOverride(
            _t("Lift the cashier policy limits on this order.")
        );
    },
});
