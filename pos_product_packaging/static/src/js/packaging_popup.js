/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { _t } from "@web/core/l10n/translation";

export class PackagingPopup extends AbstractAwaitablePopup {
    static template = "pos_product_packaging.PackagingPopup";
    static defaultProps = {
        confirmText: _t("Confirm"),
        cancelText: _t("Cancel"),
        title: _t("Select Packaging"),
    };

    setup() {
        super.setup();
        this.pos = usePos();
        this.state = useState({
            selectedPackaging: null,
            packageQty: 1,
            totalQty: 0,
            totalPrice: 0,
        });
        this.packagings = this.props.packagings || [];
        this.product = this.props.product;
    }

    selectPackaging(packaging) {
        this.state.selectedPackaging = packaging;
        this._updateTotals();
    }

    onPackageQtyChange(ev) {
        this.state.packageQty = parseFloat(ev.target.value) || 1;
        this._updateTotals();
    }

    incrementQty() {
        this.state.packageQty += 1;
        this._updateTotals();
    }

    decrementQty() {
        if (this.state.packageQty > 1) {
            this.state.packageQty -= 1;
            this._updateTotals();
        }
    }

    _updateTotals() {
        if (this.state.selectedPackaging && this.product) {
            const packagingQty = this.state.selectedPackaging.qty || 1;
            this.state.totalQty = this.state.packageQty * packagingQty;
            this.state.totalPrice = this.state.totalQty * (this.product.lst_price || 0);
        } else {
            this.state.totalQty = 0;
            this.state.totalPrice = 0;
        }
    }

    getPayload() {
        return {
            packaging: this.state.selectedPackaging,
            packageQty: this.state.packageQty,
            totalQty: this.state.totalQty,
        };
    }

    confirm() {
        if (!this.state.selectedPackaging) {
            return;
        }
        this.props.close({ confirmed: true, payload: this.getPayload() });
    }

    cancel() {
        this.props.close({ confirmed: false });
    }

    clearPackaging() {
        this.props.close({
            confirmed: true,
            payload: {
                packaging: null,
                packageQty: 0,
                totalQty: 0,
                clearPackaging: true,
            }
        });
    }
}