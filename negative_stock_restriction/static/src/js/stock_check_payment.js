/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ManagerOverridePopup } from
    "@negative_stock_restriction/js/manager_override_popup";
import {
    makeAwaitable,
    ask,
} from "@point_of_sale/app/utils/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Check stock for the current order, respecting exceptions.
 * Returns { blocked: bool, issues: string[], canOverride: bool }
 *
 * Orderlines carry product.product records (getProduct() returns product_id),
 * so this path is keyed by variant - unlike the badges, which are per template.
 */
async function checkStockForOrder(orm, pos, orderlines) {
    const productIds = [
        ...new Set(orderlines.map((l) => l.getProduct().id)),
    ];
    if (!productIds.length) {
        return { blocked: false, issues: [], canOverride: false };
    }

    const result = await orm.call(
        "pos.session",
        "get_stock_for_products",
        [productIds],
        { config_id: pos.config.id }
    );

    if (!result.enabled) {
        return { blocked: false, issues: [], canOverride: false };
    }

    const stock = result.stock;
    const exempt = result.exempt || {};
    const mode = result.mode;
    const bypass = result.bypass;
    const issues = [];

    for (const line of orderlines) {
        const pid = line.getProduct().id;
        const available = stock[pid];
        if (available === undefined || available === null) continue;

        // Skip exempt products
        if (exempt[pid]) continue;

        if (available >= line.getQuantity()) continue;

        issues.push(
            line.getProduct().display_name + ": " +
            _t("Available") + " " + parseFloat(available).toFixed(1) + ", " +
            _t("Ordered") + " " + line.getQuantity()
        );
    }

    if (issues.length === 0) {
        return { blocked: false, issues: [], canOverride: false };
    }

    const blocked = (mode === "hard" && !bypass);
    const canOverride = blocked && result.manager_override;

    return { blocked, issues, mode, bypass, canOverride };
}

/**
 * Run the check and show the popup that matches the configured mode.
 * Returns true when the caller may carry on with the original action.
 */
async function confirmStockForOrder(orm, dialog, pos, orderlines, texts) {
    let check;
    try {
        check = await checkStockForOrder(orm, pos, orderlines);
    } catch (error) {
        // Never hold the till hostage to a network or server hiccup.
        console.error("[NegStock] Stock check failed:", error);
        return true;
    }

    if (!check.issues || !check.issues.length) {
        return true;
    }

    const msg = _t("Insufficient Stock:") + "\n" + check.issues.join("\n");

    if (!check.blocked) {
        // Soft warning: let the cashier decide.
        return await ask(dialog, {
            title: _t("Low Stock Warning"),
            body: msg + "\n\n" + texts.softBody,
        });
    }

    if (check.canOverride) {
        const overrideResult = await makeAwaitable(
            dialog,
            ManagerOverridePopup,
            {
                title: _t("Manager Override Required"),
                issues: check.issues,
            }
        );
        return !!overrideResult;
    }

    dialog.add(AlertDialog, {
        title: _t("Negative Stock Blocked"),
        body: msg + "\n\n" + texts.hardBody,
    });
    return false;
}

// --- Patch PosStore.pay: block the Pay button ------------------------------

patch(PosStore.prototype, {
    async pay() {
        const order = this.getOrder();
        const orderlines = order ? order.getOrderlines() : [];

        if (orderlines.length) {
            const proceed = await confirmStockForOrder(
                this.env.services.orm, this.dialog, this, orderlines,
                {
                    softBody: _t("Do you want to proceed with negative stock?"),
                    hardBody: _t(
                        "Please adjust quantities or restock before payment."
                    ),
                }
            );
            if (!proceed) {
                return;
            }
        }
        return super.pay(...arguments);
    },
});

// --- Patch PaymentScreen: block the Validate button ------------------------

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const order = this.pos.getOrder();
        const orderlines = order ? order.getOrderlines() : [];

        if (orderlines.length) {
            const proceed = await confirmStockForOrder(
                this.env.services.orm, this.dialog, this.pos, orderlines,
                {
                    softBody: _t("Validate order with negative stock?"),
                    hardBody: _t(
                        "Cannot validate order. Go back and adjust quantities."
                    ),
                }
            );
            if (!proceed) {
                return;
            }
        }

        const result = await super.validateOrder(isForceValidate);

        // Fire refresh event so ProductScreen badges update instantly.
        // Small delay to let the order sync and stock quants update.
        setTimeout(() => {
            document.dispatchEvent(new CustomEvent("neg-stock-refresh"));
        }, 1500);

        return result;
    },
});
