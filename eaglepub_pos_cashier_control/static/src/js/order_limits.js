/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

/**
 * Price changes are blocked at the numpad rather than at setUnitPrice, because
 * setUnitPrice is also how pricelists and barcodes apply their prices. Gating
 * the mode switch stops the cashier typing a price without touching any of the
 * automatic paths.
 */
patch(ProductScreen.prototype, {
    onNumpadClick(buttonValue) {
        if (buttonValue === "price") {
            const policy = this.pos.eaglepubPolicy;
            const order = this.pos.getOrder();
            if (policy && !policy.allow_price_change && !order?.eaglepubOverridden) {
                this.pos.notification.add(
                    _t(
                        'Changing prices is not allowed by your "%s" policy. A manager can override this order.',
                        policy.name
                    ),
                    { type: "warning" }
                );
                return;
            }
        }
        return super.onNumpadClick(buttonValue);
    },
});

/**
 * The order ceiling is checked as the order is validated rather than as lines
 * are added, so a cashier can still build the order and call a manager over at
 * the end instead of being blocked halfway through.
 */
patch(OrderPaymentValidation.prototype, {
    async isOrderValid(isForceValidate) {
        const policy = this.pos.eaglepubPolicy;
        const ceiling = policy?.max_order_amount || 0;
        const order = this.order;

        if (policy && ceiling > 0 && order && !order.eaglepubOverridden) {
            const total = order.totalDue || 0;
            if (total > ceiling) {
                const granted = await this.pos.eaglepubRequestOverride(
                    _t("This order is above the limit your policy allows.")
                );
                if (!granted) {
                    this.pos.dialog.add(AlertDialog, {
                        title: _t("Manager Approval Needed"),
                        body: _t(
                            'This order comes to %(total)s, above the %(max)s ceiling set by your "%(policy)s" policy.',
                            {
                                total: this.env.utils.formatCurrency(total),
                                max: this.env.utils.formatCurrency(ceiling),
                                policy: policy.name,
                            }
                        ),
                    });
                    return false;
                }
            }
        }
        return super.isOrderValid(isForceValidate);
    },
});

/**
 * Say why a line cannot be removed.
 *
 * The refusal itself lives on PosOrder.removeOrderline, which is authoritative
 * but has no way to reach the notification service - POS model records only see
 * this.models. Catching it here as well means the cashier gets told, instead of
 * tapping remove and watching nothing happen.
 */
patch(OrderSummary.prototype, {
    _setValue(val) {
        if (val === "remove") {
            const policy = this.pos.eaglepubPolicy;
            const order = this.pos.getOrder();
            if (policy && !policy.allow_line_delete && !order?.eaglepubOverridden) {
                this.pos.notification.add(
                    _t(
                        'Removing lines is not allowed by your "%s" policy. A manager can override this order.',
                        policy.name
                    ),
                    { type: "warning" }
                );
                this.numberBuffer?.reset();
                return;
            }
        }
        return super._setValue(val);
    },
});
