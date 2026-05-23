/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { PackagingPopup } from "@pos_product_packaging/js/packaging_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

patch(PosStore.prototype, {
    /**
     * Get packaging records (product.uom) for a product.
     *
     * In Odoo 19, product.packaging is replaced by product.uom.
     * Each product.uom record links a product (product_id) to a UoM (uom_id).
     * The POS loads product.uom records matching the product's variants.
     *
     * We filter to only those marked available_in_pos and exclude the base UoM.
     */
    _getPackagingsForProduct(productTemplate) {
        const productUomModel = this.models["product.uom"];
        if (!productUomModel) {
            return [];
        }

        // Get all variant IDs for this template
        const variantIds = (productTemplate.product_variant_ids || []).map(
            (v) => (typeof v === "object" ? v.id : v)
        );

        if (variantIds.length === 0) {
            return [];
        }

        // Get base UoM id of the product template
        const baseUomId = productTemplate.uom_id?.id || productTemplate.uom_id;

        // Filter product.uom records:
        // - product_id matches one of the variants
        // - available_in_pos is checked
        // - uom_id is not the base product UoM
        const packagings = productUomModel.filter((pUom) => {
            const productId = pUom.product_id?.id || pUom.product_id;
            if (!variantIds.includes(productId)) {
                return false;
            }
            if (pUom.available_in_pos !== true) {
                return false;
            }
            // Exclude the base UoM (same as product's default UoM)
            const uomId = pUom.uom_id?.id || pUom.uom_id;
            if (uomId === baseUomId) {
                return false;
            }
            return true;
        });

        return packagings;
    },

    /**
     * Units of the product's base UoM contained in one packaging UoM.
     * In v19, uom.uom.factor is the absolute multiplier vs the category's
     * reference unit (e.g. "Box of 10 Units" -> factor = 10).
     */
    _getUomQty(packagingUom, baseUom) {
        if (!packagingUom || !packagingUom.factor) {
            return 1;
        }
        const baseFactor = baseUom?.factor || 1;
        return packagingUom.factor / baseFactor;
    },

    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        if (opts.fromPackagingPopup) {
            return await super.addLineToCurrentOrder(vals, opts, configure);
        }

        // In v19, product clicks pass { product_tmpl_id: template }
        // Barcode scans pass { product_id: product, product_tmpl_id: template }
        let productTemplate = vals.product_tmpl_id;

        // Resolve if it's just an ID
        if (typeof productTemplate === "number") {
            productTemplate = this.models["product.template"].get(productTemplate);
        }

        // If we only have product_id (edge case), get template from it
        if (!productTemplate && vals.product_id) {
            let product = vals.product_id;
            if (typeof product === "number") {
                product = this.models["product.product"].get(product);
            }
            if (product) {
                productTemplate = product.product_tmpl_id;
                if (typeof productTemplate === "number") {
                    productTemplate = this.models["product.template"].get(productTemplate);
                }
            }
        }

        if (!productTemplate) {
            return await super.addLineToCurrentOrder(vals, opts, configure);
        }

        const packagings = this._getPackagingsForProduct(productTemplate);

        if (packagings && packagings.length > 0) {
            // Build popup data: get UoM info for each packaging
            const baseUom = productTemplate.uom_id;
            const packagingData = packagings.map((pUom) => {
                const uomRecord = pUom.uom_id;
                return {
                    id: pUom.id,
                    name: uomRecord?.name || uomRecord?.display_name || "Package",
                    qty: this._getUomQty(uomRecord, baseUom),
                    record: pUom,
                };
            });

            const payload = await makeAwaitable(this.dialog, PackagingPopup, {
                title: productTemplate.display_name || productTemplate.name || "Select Packaging",
                product: productTemplate,
                packagings: packagingData,
            });

            if (payload) {
                if (payload.packaging) {
                    const line = await super.addLineToCurrentOrder(
                        { ...vals, qty: payload.totalQty },
                        { ...opts, fromPackagingPopup: true },
                        configure
                    );
                    if (line) {
                        line.packaging_id = payload.packaging.record;
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
            // User cancelled - do nothing
            return;
        }

        return await super.addLineToCurrentOrder(vals, opts, configure);
    },
});
