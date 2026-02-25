/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { ManagerOverridePopup } from
    "@negative_stock_restriction/js/manager_override_popup";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

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

// ─── Patch ProductScreen: block Pay button ──────────────────────────────────

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this._stockOrm = useService("orm");
        this._stockPopup = useService("popup");
    },

    async onClickPay() {
        const order = this.pos.get_order();
        if (!order) return super.onClickPay(...arguments);

        const orderlines = order.get_orderlines();
        if (!orderlines.length) return super.onClickPay(...arguments);

        try {
            const check = await checkStockForOrder(
                this._stockOrm, this.pos, orderlines
            );

            if (check.issues && check.issues.length > 0) {
                const msg =
                    _t("Insufficient Stock:") + "\n"
                    ;

                if (check.blocked) {
                    if (check.canOverride) {
                        // Show manager override popup
                        const { confirmed } = await this._stockPopup.add(
                            ManagerOverridePopup,
                            {
                                title: _t("Manager Override Required "),
                                issues: check.issues,
                            }
                        );
                        if (!confirmed) return; // Cancelled
                        // PIN verified → proceed
                    } else {
                        // Hard block, no override available
                        await this._stockPopup.add(ErrorPopup, {
                            title: _t("Negative Stock Blocked"),
                            body: msg + "\n\n" +
                                _t("Please adjust quantities or restock before payment.")
                                ,
                        });
                        return;
                    }
                } else {
                    // Soft warning
                    const { confirmed } = await this._stockPopup.add(
                        ConfirmPopup,
                        {
                            title: _t("Low Stock Warning"),
                            body: msg + "\n\n" +
                                _t("Do you want to proceed with negative stock?")
                                ,
                            confirmText: _t("Proceed"),
                            cancelText: _t("Cancel"),
                        }
                    );
                    if (!confirmed) return;
                }
            }
        } catch (error) {
            console.error("Stock check on pay error:", error);
            // On error, allow proceeding (don't block POS for network issues)
        }

        return super.onClickPay(...arguments);
    },
});

// ─── Patch PaymentScreen: block Validate button ─────────────────────────────

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this._stockOrm = useService("orm");
        this._stockPopup = useService("popup");
    },

    async validateOrder(isForceValidate) {
        const order = this.pos.get_order();
        if (order) {
            const orderlines = order.get_orderlines();
            if (orderlines.length) {
                try {
                    const check = await checkStockForOrder(
                        this._stockOrm, this.pos, orderlines
                    );

                    if (check.issues && check.issues.length > 0) {
                        const msg =
                            _t("Insufficient Stock:") + "\n" +
                            check.issues.join("\n")

                            ;

                        if (check.blocked) {
                            if (check.canOverride) {
                                const { confirmed } = await this._stockPopup.add(
                                    ManagerOverridePopup,
                                    {
                                        title: _t("Manager Override Required"),
                                        issues: check.issues,
                                    }
                                );
                                if (!confirmed) return;
                            } else {
                                await this._stockPopup.add(ErrorPopup, {
                                    title: _t("Negative Stock Blocked"),
                                    body: msg + "\n\n" +
                                        _t("Cannot validate order. Go back and adjust quantities.")
                                        ,
                                });
                                return;
                            }
                        } else {
                            const { confirmed } = await this._stockPopup.add(
                                ConfirmPopup,
                                {
                                    title: _t("Low Stock Warning"),
                                    body: msg + "\n\n" +
                                        _t("Validate order with negative stock?")
                                        ,
                                    confirmText: _t("Validate"),
                                    cancelText: _t("Cancel"),
                                }
                            );
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
        // Small delay to let the order sync and stock quants update
        setTimeout(() => {
            console.log("[NegStock] Order validated → dispatching refresh...");
            document.dispatchEvent(new CustomEvent("neg-stock-refresh"));
        }, 1500);

        return result;
    },
});
