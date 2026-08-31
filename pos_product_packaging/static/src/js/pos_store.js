/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { PackagingPopup } from "@pos_product_packaging/js/packaging_popup";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

patch(PosStore.prototype, {
    async syncAllOrders(options = {}) {
        const ordersBeforeSync = options.orders
            ? [...options.orders]
            : (() => {
                  const { orderToCreate, orderToUpdate } = this.getPendingOrder();
                  return [...orderToCreate, ...orderToUpdate];
              })();

        const tmplIdsToRefresh = new Set();
        for (const order of ordersBeforeSync) {
            for (const line of order?.lines || []) {
                const tmpl =
                    line.product_id?.product_tmpl_id ||
                    line.product_tmpl_id;
                const tmplId = tmpl?.id || tmpl;
                if (tmplId) {
                    tmplIdsToRefresh.add(tmplId);
                }
            }
        }

        const result = await super.syncAllOrders(options);

        if (tmplIdsToRefresh.size > 0 && !this.data.network.offline) {
            this._refreshQtyAvailable([...tmplIdsToRefresh]).catch((err) => {
                console.warn("pos_product_packaging: qty refresh failed", err);
            });
        }

        return result;
    },

    async _refreshQtyAvailable(templateIds) {
        if (!templateIds || templateIds.length === 0) {
            return;
        }
        const records = await this.data.call(
            "product.template",
            "read",
            [templateIds, ["qty_available"]]
        );
        const tmplModel = this.models["product.template"];
        if (!tmplModel) {
            return;
        }
        for (const rec of records || []) {
            const local = tmplModel.get(rec.id);
            if (local) {
                local.qty_available = rec.qty_available;
            }
        }
    },

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
        // In Odoo 19, packagings are uom.uom records linked to the
        // product.template via the uom_ids many2many field (not a
        // separate product.uom link table).
        const uomIds = productTemplate.uom_ids || [];

        if (!uomIds || uomIds.length === 0) {
            return [];
        }

        const baseUomId = productTemplate.uom_id?.id || productTemplate.uom_id;

        const packagings = uomIds.filter((uomRec) => {
            if (uomRec.available_in_pos !== true) {
                return false;
            }
            const uomId = uomRec.id;
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
                return {
                    id: pUom.id,
                    name: pUom.name || pUom.display_name || "Package",
                    qty: this._getUomQty(pUom, baseUom),
                    record: pUom,
                };
            });

            // Pricelist-aware unit price (falls back to list_price if pricelist absent)
            const order = this.getOrder();
            const pricelist = order?.pricelist_id;
            const fiscalPosition = order?.fiscal_position_id;
            const unitPrice = productTemplate.getPrice
                ? productTemplate.getPrice(pricelist, 1)
                : productTemplate.list_price || 0;

            const popupProps = {
                title: productTemplate.display_name || productTemplate.name || "Select Packaging",
                product: productTemplate,
                packagings: packagingData,
                unitPrice: unitPrice,
            };
            if (pricelist) {
                popupProps.pricelist = pricelist;
            }
            if (fiscalPosition) {
                popupProps.fiscalPosition = fiscalPosition;
            }
            const payload = await makeAwaitable(this.dialog, PackagingPopup, popupProps);

            if (payload) {
                if (payload.packaging) {
                    const line = await super.addLineToCurrentOrder(
                        {
                            ...vals,
                            qty: payload.totalQty,
                            packaging_id: payload.packaging.record,
                            package_qty: payload.packageQty,
                        },
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
