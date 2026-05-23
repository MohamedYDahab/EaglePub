/** @odoo-module */

import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { Component, useState } from "@odoo/owl";

export class PackagingPopup extends Component {
    static template = "pos_product_packaging.PackagingPopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        product: { type: Object, optional: true },
        packagings: { type: Array, optional: true },
        unitPrice: { type: Number, optional: true },
        pricelist: { type: Object, optional: true },
        fiscalPosition: { type: Object, optional: true },
        close: { type: Function },
        getPayload: { type: Function, optional: true },
    };
    static defaultProps = {
        title: "Select Packaging",
        packagings: [],
        unitPrice: 0,
    };

    setup() {
        this.pos = usePos();
        this.state = useState({
            selectedPackaging: null,
            packageQty: 1,
            totalQty: 0,
            totalPrice: 0,
            packagePrice: 0,
            totalTax: 0,
            totalPriceIncl: 0,
        });
        this.packagings = this.props.packagings || [];
        this.product = this.props.product;
        this.unitPrice = this.props.unitPrice || this.product?.list_price || 0;
    }

    formatCurrency(value) {
        return this.env.utils.formatCurrency(value);
    }

    _computeTaxAmounts(quantity) {
        if (!this.product?.getTaxDetails || quantity <= 0) {
            return { excl: this.unitPrice * quantity, incl: this.unitPrice * quantity, tax: 0 };
        }
        try {
            const details = this.product.getTaxDetails({
                overridedValues: {
                    price: this.unitPrice,
                    quantity: quantity,
                    pricelist: this.props.pricelist || false,
                    fiscalPosition: this.props.fiscalPosition || false,
                },
            });
            const excl = details?.raw_total_excluded_currency ?? this.unitPrice * quantity;
            const incl = details?.raw_total_included_currency ?? excl;
            return { excl, incl, tax: incl - excl };
        } catch (e) {
            console.warn("pos_product_packaging: tax computation failed", e);
            const fallback = this.unitPrice * quantity;
            return { excl: fallback, incl: fallback, tax: 0 };
        }
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
            this.state.totalPrice = this.state.totalQty * this.unitPrice;
            this.state.packagePrice = packagingQty * this.unitPrice;

            const tax = this._computeTaxAmounts(this.state.totalQty);
            this.state.totalPriceExcl = tax.excl;
            this.state.totalPriceIncl = tax.incl;
            this.state.totalTax = tax.tax;
        } else {
            this.state.totalQty = 0;
            this.state.totalPrice = 0;
            this.state.packagePrice = 0;
            this.state.totalPriceExcl = 0;
            this.state.totalPriceIncl = 0;
            this.state.totalTax = 0;
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
