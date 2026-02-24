/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosDB } from "@point_of_sale/app/store/db";
import { patch } from "@web/core/utils/patch";
import { PackagingPopup } from "@pos_product_packaging/js/packaging_popup";

// Patch PosDB to also store packagings by product_id
patch(PosDB.prototype, {
    add_packagings(packagings) {
        // Call original method first
        super.add_packagings(packagings);

        // Initialize our storage
        if (!this.packaging_by_product_id) {
            this.packaging_by_product_id = {};
        }

        // Index all packagings by product_id
        for (const packaging of packagings) {
            // Skip if available_in_pos is explicitly false
            if (packaging.available_in_pos === false) {
                continue;
            }

            const productId = packaging.product_id ? packaging.product_id[0] : null;
            if (productId) {
                if (!this.packaging_by_product_id[productId]) {
                    this.packaging_by_product_id[productId] = [];
                }
                // Avoid duplicates
                const exists = this.packaging_by_product_id[productId].some(p => p.id === packaging.id);
                if (!exists) {
                    this.packaging_by_product_id[productId].push(packaging);
                }
            }
        }

        console.log("All packagings indexed by product_id:", this.packaging_by_product_id);
    },
});

// Patch PosStore
patch(PosStore.prototype, {
    getPackagingsForProduct(productId) {
        return this.db.packaging_by_product_id?.[productId] || [];
    },

    async addProductToCurrentOrder(product, options = {}) {
        if (Number.isInteger(product)) {
            product = this.db.get_product_by_id(product);
        }

        if (options.fromPackagingPopup) {
            return await super.addProductToCurrentOrder(product, options);
        }

        const packagings = this.getPackagingsForProduct(product.id);

        if (packagings && packagings.length > 0) {
            const { confirmed, payload } = await this.popup.add(PackagingPopup, {
                title: product.display_name,
                product: product,
                packagings: packagings,
            });

            if (confirmed && payload) {
                if (payload.packaging) {
                    this.get_order() || this.add_new_order();
                    const newOptions = {
                        ...(await product.getAddProductOptions()),
                        quantity: payload.totalQty,
                        fromPackagingPopup: true,
                    };

                    if (!Object.keys(newOptions).length) {
                        return;
                    }

                    const line = await this.addProductFromUi(product, newOptions);
                    if (line) {
                        line.packaging_id = payload.packaging;
                        line.package_qty = payload.packageQty;
                    }
                    this.numberBuffer.reset();
                    return line;
                } else if (payload.clearPackaging) {
                    return await super.addProductToCurrentOrder(product, { ...options, fromPackagingPopup: true });
                }
            }
            return;
        }

        return await super.addProductToCurrentOrder(product, options);
    },
});