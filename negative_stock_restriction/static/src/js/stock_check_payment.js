/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

/**
 * Helper: check stock for the current order.
 * Returns { blocked: bool, issues: string[] }
 */
async function checkStockForOrder(orm, pos, orderlines) {
    const productIds = [
        ...new Set(orderlines.map((l) => l.get_product().id)),
    ];
    if (!productIds.length) {
        return { blocked: false, issues: [] };
    }

    const result = await orm.call(
        "pos.session",
        "get_stock_for_products",
        [productIds]
    );

    if (!result.enabled) {
        return { blocked: false, issues: [] };
    }

    const stock = result.stock;
    const mode = result.mode;
    const bypass = result.bypass;
    const issues = [];

    for (const line of orderlines) {
        const pid = line.get_product().id;
        const available = stock[pid];
        if (available === undefined || available === null) continue;
        if (available >= line.get_quantity()) continue;
        issues.push(
            line.get_product().display_name + ": " +
            _t("Available") + " " + available + ", " +
            _t("Ordered") + " " + line.get_quantity()
        );
    }

    if (issues.length === 0) {
        return { blocked: false, issues: [] };
    }

    // Hard block: completely prevent (unless bypass user)
    // Soft warning: show warning, let user decide
    const blocked = (mode === "hard" && !bypass);
    return { blocked, issues, mode, bypass };
}

// ─── Patch ProductScreen: block Pay button ───────────────────────────────────

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this._stockOrm = useService("orm");
        this._stockPopup = useService("popup");
    },

    async onClickPay() {
        const order = this.pos.get_order();
        if (!order) {
            return super.onClickPay(...arguments);
        }

        const orderlines = order.get_orderlines();
        if (!orderlines.length) {
            return super.onClickPay(...arguments);
        }

        try {
            const check = await checkStockForOrder(this._stockOrm, this.pos, orderlines);

            if (check.issues && check.issues.length > 0) {
                const msg = _t("Insufficient Stock:") + "\n" +
                    check.issues.join("\n") + "\n\n" +
                    "مخزون غير كافٍ";

                if (check.blocked) {
                    // Hard block: cannot proceed
                    await this._stockPopup.add(ErrorPopup, {
                        title: _t("Negative Stock Blocked / تم حظر المخزون السالب"),
                        body: msg + "\n\n" +
                              _t("Please adjust quantities or restock before payment.") + "\n" +
                              "يرجى تعديل الكميات أو إعادة التخزين قبل الدفع",
                    });
                    return; // ← BLOCK: do NOT proceed to payment
                } else {
                    // Soft warning: ask confirmation
                    const { confirmed } = await this._stockPopup.add(ConfirmPopup, {
                        title: _t("Low Stock Warning / تحذير مخزون منخفض"),
                        body: msg + "\n\n" +
                              _t("Do you want to proceed with negative stock?") + "\n" +
                              "هل تريد المتابعة بمخزون سالب؟",
                        confirmText: _t("Proceed"),
                        cancelText: _t("Cancel"),
                    });
                    if (!confirmed) {
                        return; // ← User cancelled
                    }
                    // User confirmed → fall through to super
                }
            }
        } catch (error) {
            console.error("Stock check on pay error:", error);
            // On error, allow proceeding (don't block POS due to network issues)
        }

        return super.onClickPay(...arguments);
    },
});

// ─── Patch PaymentScreen: block Validate button (secondary safeguard) ────────

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
                        const msg = _t("Insufficient Stock:") + "\n" +
                            check.issues.join("\n") + "\n\n" +
                            "مخزون غير كافٍ";

                        if (check.blocked) {
                            await this._stockPopup.add(ErrorPopup, {
                                title: _t("Negative Stock Blocked / تم حظر المخزون السالب"),
                                body: msg + "\n\n" +
                                      _t("Cannot validate order. Go back and adjust quantities.") + "\n" +
                                      "لا يمكن تأكيد الطلب. عُد وعدّل الكميات",
                            });
                            return; // ← BLOCK validation
                        } else {
                            const { confirmed } = await this._stockPopup.add(ConfirmPopup, {
                                title: _t("Low Stock Warning / تحذير مخزون منخفض"),
                                body: msg + "\n\n" +
                                      _t("Validate order with negative stock?") + "\n" +
                                      "تأكيد الطلب بمخزون سالب؟",
                                confirmText: _t("Validate"),
                                cancelText: _t("Cancel"),
                            });
                            if (!confirmed) {
                                return; // ← User cancelled
                            }
                        }
                    }
                } catch (error) {
                    console.error("Stock check on validate error:", error);
                }
            }
        }

        return super.validateOrder(isForceValidate);
    },
});
