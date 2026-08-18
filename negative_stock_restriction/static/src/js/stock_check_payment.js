/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";
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
 * Run the check and show the popup that matches the configured mode.
 * Returns true when the caller may carry on with the original action.
 */
async function confirmStockForOrder(orm, popup, pos, orderlines, texts) {
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
        const { confirmed } = await popup.add(ConfirmPopup, {
            title: _t("Low Stock Warning"),
            body: msg + "\n\n" + texts.softBody,
            confirmText: texts.confirmText,
            cancelText: _t("Cancel"),
        });
        return Boolean(confirmed);
    }

    if (check.canOverride) {
        const { confirmed } = await popup.add(ManagerOverridePopup, {
            title: _t("Manager Override Required"),
            issues: check.issues,
        });
        return Boolean(confirmed);
    }

    await popup.add(ErrorPopup, {
        title: _t("Negative Stock Blocked"),
        body: msg + "\n\n" + texts.hardBody,
    });
    return false;
}

// --- Patch Order.pay: block the Pay button ---------------------------------
//
// ProductScreen.onClickPay is dead code in Odoo 17 (see the FIXME in core);
// both the actionpad and the mobile switchpane call order.pay() directly, so
// that is where the check has to sit.

patch(Order.prototype, {
    async pay() {
        const orderlines = this.get_orderlines();
        if (orderlines.length) {
            const proceed = await confirmStockForOrder(
                this.env.services.orm,
                this.env.services.popup,
                this.pos,
                orderlines,
                {
                    softBody: _t("Do you want to proceed with negative stock?"),
                    confirmText: _t("Proceed"),
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

// --- Patch PaymentScreen: block Validate button ----------------------------

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this._stockOrm = useService("orm");
        this._stockPopup = useService("popup");
    },

    async validateOrder(isForceValidate) {
        const order = this.pos.get_order();
        const orderlines = order ? order.get_orderlines() : [];

        if (orderlines.length) {
            const proceed = await confirmStockForOrder(
                this._stockOrm,
                this._stockPopup,
                this.pos,
                orderlines,
                {
                    softBody: _t("Validate order with negative stock?"),
                    confirmText: _t("Validate"),
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
