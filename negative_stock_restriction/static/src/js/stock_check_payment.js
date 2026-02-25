/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ManagerOverridePopup } from
    "@negative_stock_restriction/js/manager_override_popup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { ask } from "@point_of_sale/app/store/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Check stock for the current order, respecting exceptions.
 * Returns { blocked: bool, issues: string[], canOverride: bool }
 */
async function checkStockForOrder(orm, pos, orderlines) {
    const productIds = [
        ...new Set(orderlines.map((l) => l.get_product().id)),
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
        const pid = line.get_product().id;
        const available = stock[pid];
        if (available === undefined || available === null) continue;

        // Skip exempt products
        if (exempt[pid]) continue;

        if (available >= line.get_quantity()) continue;

        issues.push(
            line.get_product().display_name + ": " +
            _t("Available") + " " + parseFloat(available).toFixed(1) + ", " +
            _t("Ordered") + " " + line.get_quantity()
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
        const currentOrder = this.get_order();
        if (currentOrder) {
            const orderlines = currentOrder.get_orderlines();
            if (orderlines.length) {
                try {
                    const orm = this.env.services.orm;
                    const dialog = this.env.services.dialog;
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
        const order = this.pos.get_order();
        if (order) {
            const orderlines = order.get_orderlines();
            if (orderlines.length) {
                try {
                    const orm = this.env.services.orm;
                    const check = await checkStockForOrder(orm, this.pos, orderlines);

                    if (check.issues && check.issues.length > 0) {
                        const msg = _t("Insufficient Stock:") + "\n" +
                            check.issues.join("\n");

                        if (check.blocked) {
                            if (check.canOverride) {
                                const overrideResult = await makeAwaitable(
                                    this.dialog,
                                    ManagerOverridePopup,
                                    {
                                        title: _t("Manager Override Required"),
                                        issues: check.issues,
                                    }
                                );
                                if (!overrideResult) return;
                            } else {
                                this.dialog.add(AlertDialog, {
                                    title: _t("Negative Stock Blocked"),
                                    body: msg + "\n\n" +
                                        _t("Cannot validate order. Go back and adjust quantities."),
                                });
                                return;
                            }
                        } else {
                            const confirmed = await ask(this.dialog, {
                                title: _t("Low Stock Warning"),
                                body: msg + "\n\n" +
                                    _t("Validate order with negative stock?"),
                            });
                            if (!confirmed) return;
                        }
                    }
                } catch (error) {
                    console.error("Stock check on validate error:", error);
                }
            }
        }

        const result = await super.validateOrder(isForceValidate);

        // ── Fire refresh event so ProductScreen badges update instantly ──
        setTimeout(() => {
            console.log("[NegStock] Order validated → dispatching refresh...");
            document.dispatchEvent(new CustomEvent("neg-stock-refresh"));
        }, 1500);

        return result;
    },
});
