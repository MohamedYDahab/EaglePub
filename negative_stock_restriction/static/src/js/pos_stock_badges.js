/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount } from "@odoo/owl";

/**
 * This module patches ProductScreen to:
 * 1. Fetch stock for the product templates currently on screen
 * 2. Inject stock badges into product cards via DOM manipulation
 * 3. Auto-hide out-of-stock products if configured
 * 4. Refresh stock INSTANTLY after every completed order
 *    (via custom "neg-stock-refresh" event fired by validateOrder)
 * 5. Refresh on browser tab visibility change (user switches back)
 * 6. Refresh on configurable interval (default 15s, 0 = disabled)
 * 7. Re-apply badges on DOM changes (category switches, search, scroll)
 *
 * Note on ids: since Odoo 18 the product screen renders product.template
 * records, so data-product-id on each card is a TEMPLATE id. The backend
 * keys its badge map by template to match.
 */

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this._badgeOrm = useService("orm");
        // Plain object, not useState: badges are written straight to the DOM
        // and must never trigger an Owl re-render of the product list.
        this._negStock = { stockData: {}, settings: null };

        this._onNegStockRefresh = () => this.refreshNegStock();

        this._onVisibilityChange = () => {
            if (document.visibilityState === "visible") {
                this.refreshNegStock();
            }
        };

        onMounted(async () => {
            await this._loadNegStockSettings();
            await this.refreshNegStock();

            document.addEventListener(
                "neg-stock-refresh", this._onNegStockRefresh
            );
            document.addEventListener(
                "visibilitychange", this._onVisibilityChange
            );

            const settings = this._negStock.settings;
            const interval = settings ? settings.refresh_interval : 15;
            if (interval > 0) {
                this._stockRefreshInterval = setInterval(
                    () => this.refreshNegStock(), interval * 1000
                );
            }

            // Re-apply badges when the product list changes (category switch,
            // search, scroll). Templates that appeared since the last fetch
            // have no stock data yet, so pull it in for them.
            this._badgeObserver = new MutationObserver(() => {
                clearTimeout(this._badgeDebounce);
                this._badgeDebounce = setTimeout(() => {
                    if (this._hasUnknownProducts()) {
                        this.refreshNegStock();
                    } else {
                        this._applyStockBadges();
                    }
                }, 150);
            });
            this._observeProductList();
        });

        onWillUnmount(() => {
            document.removeEventListener(
                "neg-stock-refresh", this._onNegStockRefresh
            );
            document.removeEventListener(
                "visibilitychange", this._onVisibilityChange
            );
            clearInterval(this._stockRefreshInterval);
            clearTimeout(this._badgeDebounce);
            if (this._badgeObserver) {
                this._badgeObserver.disconnect();
            }
        });
    },

    /**
     * Odoo 19 renders one .product-list per category, and Owl re-creates
     * them, so watch a stable ancestor instead of a single container.
     */
    _observeProductList() {
        if (!this._badgeObserver) {
            return;
        }
        const root =
            document.querySelector(".product-list")?.parentElement ||
            document.querySelector(".product-screen") ||
            document.body;
        this._badgeObserver.observe(root, { childList: true, subtree: true });
    },

    _negStockCards() {
        return document.querySelectorAll(
            ".product-list article.product[data-product-id]"
        );
    },

    /** These are product.template ids, not variant ids. */
    _visibleTemplateIds() {
        return [...this._negStockCards()].map(
            (card) => parseInt(card.dataset.productId)
        );
    },

    _hasUnknownProducts() {
        const stockData = this._negStock.stockData;
        return this._visibleTemplateIds().some((id) => !(id in stockData));
    },

    _negStockActive() {
        const settings = this._negStock.settings;
        return Boolean(
            settings && settings.enabled && settings.pos_enabled &&
            settings.show_in_pos
        );
    },

    async _loadNegStockSettings() {
        try {
            this._negStock.settings = await this._badgeOrm.call(
                "pos.session", "get_neg_stock_settings", []
            );
        } catch (e) {
            console.error("[NegStock] Failed to load settings:", e);
        }
    },

    async _loadStockData() {
        if (!this._negStockActive()) {
            return;
        }
        const templateIds = this._visibleTemplateIds();
        if (!templateIds.length) {
            return;
        }
        try {
            const data = await this._badgeOrm.call(
                "pos.session", "get_all_product_stock", [],
                {
                    config_id: this.pos.config.id,
                    product_tmpl_ids: templateIds,
                }
            );
            Object.assign(this._negStock.stockData, data || {});
        } catch (e) {
            console.error("[NegStock] Failed to load stock data:", e);
        }
    },

    /** Force a refresh; safe to call from anywhere. */
    async refreshNegStock() {
        await this._loadStockData();
        this._applyStockBadges();
    },

    _applyStockBadges() {
        if (!this._negStockActive()) {
            return;
        }
        // Injecting badges mutates the very subtree we observe, which would
        // retrigger the observer forever. Pause it for the duration.
        if (this._badgeObserver) {
            this._badgeObserver.disconnect();
        }
        try {
            this._renderStockBadges();
        } finally {
            this._observeProductList();
        }
    },

    _renderStockBadges() {
        const settings = this._negStock.settings;
        const stockData = this._negStock.stockData;
        const threshold = settings.threshold || 0;
        const hideOOS = settings.hide_out_of_stock || false;

        this._negStockCards().forEach((card) => {
            const templateId = parseInt(card.dataset.productId);

            const existing = card.querySelector(".neg-stock-badge");
            if (existing) {
                existing.remove();
            }

            const qty = stockData[templateId];
            // No entry means the template is not storable - nothing to show.
            if (qty === undefined || qty === null) {
                card.classList.remove("neg-stock-hidden");
                return;
            }

            const roundedQty = Math.floor(qty * 10) / 10; // 1 decimal

            if (hideOOS && roundedQty <= 0) {
                card.classList.add("neg-stock-hidden");
                return;
            }
            card.classList.remove("neg-stock-hidden");

            let badgeClass = "neg-stock-badge-green";
            if (roundedQty <= 0) {
                badgeClass = "neg-stock-badge-red";
            } else if (roundedQty <= threshold) {
                badgeClass = "neg-stock-badge-yellow";
            }

            const badge = document.createElement("div");
            badge.className = "neg-stock-badge " + badgeClass;
            badge.textContent = roundedQty;
            card.appendChild(badge);
        });
    },
});
