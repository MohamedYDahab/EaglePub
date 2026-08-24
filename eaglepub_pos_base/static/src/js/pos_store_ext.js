/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ManagerPinDialog } from "@eaglepub_pos_base/js/pin_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    /**
     * Authorise a restricted action, returning true when it may go ahead.
     *
     * Members of the POS Manager Override group pass straight through; everyone
     * else is asked for the PIN, which the server checks.
     *
     * @param {string} reason shown in the dialog so the cashier knows what is
     *                        being authorised
     * @returns {Promise<boolean>}
     */
    async askManagerPin(reason = "") {
        if (this.cashier?.eaglepub_pos_manager) {
            return true;
        }
        const pin = await makeAwaitable(this.dialog, ManagerPinDialog, { reason });
        if (!pin) {
            return false;
        }
        const ok = await this.data.call("pos.config", "verify_eaglepub_pin", [
            this.config.id,
            pin,
        ]);
        if (!ok) {
            this.notification.add(_t("Wrong manager PIN."), { type: "danger" });
        }
        return Boolean(ok);
    },
});
