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
        [productIds]
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
 * Handle the stock check result: show appropriate popup and return
 * true if the action should proceed, false if blocked.
 */
async function handleStockCheck(dialog, check) {
    if (!check.issues || check.issues.length === 0) {
        return true;
    }

    const msg = _t("Insufficient Stock:") + "\n" + check.issues.join("\n");

    if (check.blocked) {
        if (check.canOverride) {
            // Show manager override popup
            const overrideResult = await makeAwaitable(
                dialog,
                ManagerOverridePopup,
                {
                    title: _t("Manager Override Required"),
                    issues: check.issues,
                }
            );
            return !!overrideResult;
        } else {
            // Hard block, no override available
            dialog.add(AlertDialog, {
                title: _t("Negative Stock Blocked"),
                body: msg + "\n\n" +
                    _t("Please adjust quantities or restock before payment."),
            });
            return false;
        }
    } else {
        // Soft warning
        const confirmed = await ask(dialog, {
            title: _t("Low Stock Warning"),
            body: msg + "\n\n" +
                _t("Do you want to proceed with negative stock?"),
        });
        return confirmed;
    }
}

// ─── Patch PosStore: intercept pay() flow ───────────────────────────────────

patch(PosStore.prototype, {
    async pay() {
        const currentOrder = this.getOrder();
        if (currentOrder) {
            const orderlines = currentOrder.getOrderlines();
            if (orderlines.length) {
                try {
                    const orm = this.env.services.orm;
                    const dialog = this.dialog;
                    const check = await checkStockForOrder(orm, this, orderlines);
                    const canProceed = await handleStockCheck(dialog, check);
                    if (!canProceed) return;
                } catch (error) {
                    console.error("Stock check on pay error:", error);
                    // On error, allow proceeding (don't block POS for network issues)
                }
            }
        }
        return super.pay(...arguments);
    },
});

// ─── Patch PaymentScreen: block Validate button ─────────────────────────────

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const result = await super.validateOrder(isForceValidate);

        // ── Fire refresh event so ProductScreen badges update instantly ──
        setTimeout(() => {
            console.log("[NegStock] Order validated → dispatching refresh...");
            document.dispatchEvent(new CustomEvent("neg-stock-refresh"));
        }, 1500);

        return result;
    },
});
