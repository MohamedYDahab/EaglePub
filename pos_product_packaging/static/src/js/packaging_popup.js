/** @odoo-module */

import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component, useState } from "@odoo/owl";

export class PackagingPopup extends Component {
    static template = "pos_product_packaging.PackagingPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        product: { type: Object, optional: true },
        packagings: { type: Array, optional: true },
        close: { type: Function },
        getPayload: { type: Function, optional: true },
    };
    static defaultProps = {
        title: "Select Packaging",
        packagings: [],
    };

    setup() {
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

    confirm() {
        if (!this.state.selectedPackaging) {
            return;
        }
        const payload = {
            packaging: this.state.selectedPackaging,
            packageQty: this.state.packageQty,
            totalQty: this.state.totalQty,
        };
        if (this.props.getPayload) {
            this.props.getPayload(payload);
        }
        this.props.close();
    }

    cancel() {
        this.props.close();
    }

    clearPackaging() {
        const payload = {
            packaging: null,
            packageQty: 0,
            totalQty: 0,
            clearPackaging: true,
        };
        if (this.props.getPayload) {
            this.props.getPayload(payload);
        }
        this.props.close();
    }
}
