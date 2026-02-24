/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { PackagingPopup } from "@pos_product_packaging/js/packaging_popup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";

patch(PosStore.prototype, {
    _getPackagingsForProduct(productId) {
        const packagingModel = this.models["product.packaging"];
        if (!packagingModel) {
            return [];
        }
        return packagingModel.filter(
            (p) => p.product_id?.id === productId && p.available_in_pos !== false
        );
    },

    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        if (opts.fromPackagingPopup) {
            return await super.addLineToCurrentOrder(vals, opts, configure);
        }

        // Resolve the product object
        let product = vals.product_id;
        if (typeof product === "number") {
            product = this.models["product.product"].get(product);
        }
        if (!product) {
            return await super.addLineToCurrentOrder(vals, opts, configure);
        }

        const packagings = this._getPackagingsForProduct(product.id);

        if (packagings && packagings.length > 0) {
            const payload = await makeAwaitable(this.dialog, PackagingPopup, {
                title: product.display_name || product.name || "Select Packaging",
                product: product,
                packagings: packagings,
            });

            if (payload) {
                if (payload.packaging) {
                    const line = await super.addLineToCurrentOrder(
                        { ...vals, qty: payload.totalQty },
                        { ...opts, fromPackagingPopup: true },
                        configure
                    );
                    if (line) {
                        line.packaging_id = payload.packaging;
                        line.package_qty = payload.packageQty;
                    }
                    return line;
                } else if (payload.clearPackaging) {
                    return await super.addLineToCurrentOrder(
                        vals,
                        { ...opts, fromPackagingPopup: true },
                        configure
                    );
                }
            }
            return;
        }

        return await super.addLineToCurrentOrder(vals, opts, configure);
    },
});
