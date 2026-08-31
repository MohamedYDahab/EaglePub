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
     * The packagings a product offers.
     *
     * In Odoo 19 a packaging is a uom.uom record listed in
     * product.template.uom_ids - the field Odoo labels "Packagings".
     * product.uom is something else: a link table carrying a barcode for one
     * product + unit pair, with barcode required, so it is empty unless
     * somebody has been assigning barcodes. Reading it found nothing, which is
     * why the popup never appeared.
     */
    _getPackagingsForProduct(productTemplate) {
        const packagingUoms = productTemplate.uom_ids || [];
        if (packagingUoms.length === 0) {
            return [];
        }

        const baseUomId = productTemplate.uom_id?.id || productTemplate.uom_id;

        // Offer only units that were ticked for POS, and never the product's
        // own selling unit - "1 x Unit" is not a packaging choice.
        return packagingUoms.filter(
            (uom) => uom.available_in_pos === true && uom.id !== baseUomId
        );
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
            const packagingData = packagings.map((uom) => ({
                id: uom.id,
                name: uom.name || uom.display_name || "Package",
                qty: this._getUomQty(uom, baseUom),
                record: uom,
            }));

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
                    // These have to travel in vals rather than be assigned to
                    // the returned line: the merge check runs inside
                    // addLineToCurrentOrder, so a line whose packaging is set
                    // afterwards has already been merged with the wrong one.
                    // The returned line may also be a different, pre-existing
                    // line that this one merged into.
                    return await super.addLineToCurrentOrder(
                        {
                            ...vals,
                            qty: payload.totalQty,
                            packaging_id: payload.packaging.record,
                            package_qty: payload.packageQty,
                        },
                        { ...opts, fromPackagingPopup: true },
                        configure
                    );
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
