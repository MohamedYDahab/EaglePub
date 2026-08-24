/** @odoo-module */

import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

/**
 * Policy lookup lives on the order rather than the store, because POS model
 * records reach data through this.models and have no handle on the store.
 * Reading it off order.user_id keeps the rule enforceable from inside the
 * model, which is the one place every edit has to pass through.
 */
function policyOf(order) {
    if (!order || order.eaglepubOverridden) {
        return null;
    }
    return order.user_id?.eaglepub_pos_policy_id || null;
}

patch(PosStore.prototype, {
    /** Policy of whoever is at the till, or null when unrestricted. */
    get eaglepubPolicy() {
        return this.cashier?.eaglepub_pos_policy_id || null;
    },

    /**
     * Lift the policy on the current order once a manager authorises.
     * The flag rides on the order, so it lapses when that order is finished.
     */
    async eaglepubRequestOverride(reason) {
        const order = this.getOrder();
        if (!order) {
            return false;
        }
        if (order.eaglepubOverridden) {
            return true;
        }
        const granted = await this.askManagerPin(reason);
        if (granted) {
            order.eaglepubOverridden = true;
            this.notification.add(_t("Manager override applied to this order."), {
                type: "success",
            });
        }
        return granted;
    },
});

patch(PosOrder.prototype, {
    removeOrderline(line) {
        const policy = policyOf(this);
        if (policy && !policy.allow_line_delete) {
            return false;
        }
        return super.removeOrderline(line);
    },
});

patch(PosOrderline.prototype, {
    setDiscount(discount) {
        const policy = policyOf(this.order_id);
        if (policy) {
            const ceiling = policy.max_discount ?? 100;
            const requested = parseFloat(discount) || 0;
            if (requested > ceiling) {
                // Clamp rather than refuse: the cashier still gets the discount
                // they are entitled to, instead of silently getting none.
                return super.setDiscount(ceiling);
            }
        }
        return super.setDiscount(discount);
    },

    /**
     * Blocking removeOrderline on its own left the door open: a cashier who
     * cannot delete a line can still type 0 into the quantity, which empties it
     * to the same effect. Zero and negative quantities are therefore refused
     * under the same rule.
     *
     * Returning {title, body} rather than throwing is deliberate - it is the
     * contract core already uses for a rejected quantity, so the till shows a
     * proper dialog without this module wiring up its own.
     */
    setQuantity(quantity, keep_price) {
        const policy = policyOf(this.order_id);
        if (policy && !policy.allow_line_delete && !this.eaglepubIsRefundContext) {
            const quant =
                typeof quantity === "number"
                    ? quantity
                    : parseFloat("" + (quantity ? quantity : 0));
            if (quant <= 0) {
                return {
                    title: _t("Line cannot be emptied"),
                    body: _t(
                        'Your "%s" policy does not allow removing lines, and zeroing the quantity does the same thing. A manager can override this order.',
                        policy.name
                    ),
                };
            }
        }
        return super.setQuantity(quantity, keep_price);
    },

    /**
     * Refunds and return presets legitimately carry zero or negative
     * quantities, so the rule above must not touch them.
     */
    get eaglepubIsRefundContext() {
        return Boolean(this.order_id?.preset_id?.is_return || this.refunded_orderline_id);
    },
});
