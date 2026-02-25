/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount, useState } from "@odoo/owl";

/**
 * This module patches ProductScreen to:
 * 1. Fetch stock data for all products on load
 * 2. Inject stock badges into product cards via DOM manipulation
 * 3. Auto-hide out-of-stock products if configured
 * 4. Refresh stock INSTANTLY after every completed order
 *    (via custom "neg-stock-refresh" event fired by validateOrder)
 * 5. Refresh on browser tab visibility change (user switches back)
 * 6. Refresh on configurable interval (default 15s, 0 = disabled)
 * 7. Re-apply badges on DOM changes (category switches)
 */

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this._badgeOrm = useService("orm");
        this._negStockState = useState({
            stockData: {},
            settings: null,
            loaded: false,
        });

        // ── Bound event handlers (so we can removeEventListener) ──
        this._onNegStockRefresh = async () => {
            console.log("[NegStock] Order completed → refreshing stock...");
            await this._loadStockData();
            this._applyStockBadges();
        };

        this._onVisibilityChange = async () => {
            if (document.visibilityState === "visible") {
                console.log("[NegStock] Tab visible → refreshing stock...");
                await this._loadStockData();
                this._applyStockBadges();
            }
        };

        onMounted(async () => {
            // Load settings & initial stock data
            await this._loadNegStockSettings();
            await this._loadStockData();
            this._applyStockBadges();

            // ── 1. Listen for order-completed refresh events ──
            document.addEventListener(
                "neg-stock-refresh", this._onNegStockRefresh
            );

            // ── 2. Listen for tab visibility changes ──
            document.addEventListener(
                "visibilitychange", this._onVisibilityChange
            );

            // ── 3. Configurable auto-refresh interval ──
            const interval = this._negStockState.settings
                ? this._negStockState.settings.refresh_interval
                : 15;

            if (interval && interval > 0) {
                this._stockRefreshInterval = setInterval(async () => {
                    await this._loadStockData();
                    this._applyStockBadges();
                }, interval * 1000); // convert seconds to ms
            }

            // ── 4. MutationObserver: re-apply badges on DOM changes ──
            //    (category switches, search results, scroll load)
            this._badgeObserver = new MutationObserver(() => {
                clearTimeout(this._badgeDebounce);
                this._badgeDebounce = setTimeout(() => {
                    this._applyStockBadges();
                }, 150);
            });

            // Odoo 18: product list container selector
            const container = document.querySelector(".product-list") ||
                document.querySelector(".o_product_list");
            if (container) {
                this._badgeObserver.observe(container, {
                    childList: true,
                    subtree: true,
                });
            }
        });

        onWillUnmount(() => {
            // Clean up everything
            document.removeEventListener(
                "neg-stock-refresh", this._onNegStockRefresh
            );
            document.removeEventListener(
                "visibilitychange", this._onVisibilityChange
            );
            if (this._stockRefreshInterval) {
                clearInterval(this._stockRefreshInterval);
            }
            if (this._badgeObserver) {
                this._badgeObserver.disconnect();
            }
            if (this._badgeDebounce) {
                clearTimeout(this._badgeDebounce);
            }
        });
    },

    async _loadNegStockSettings() {
        try {
            const settings = await this._badgeOrm.call(
                "pos.session",
                "get_neg_stock_settings",
                []
            );
            this._negStockState.settings = settings;
        } catch (e) {
            console.error("[NegStock] Failed to load settings:", e);
        }
    },

    async _loadStockData() {
        const settings = this._negStockState.settings;
        if (!settings || !settings.enabled || !settings.pos_enabled ||
            !settings.show_in_pos) {
            return;
        }

        try {
            const data = await this._badgeOrm.call(
                "pos.session",
                "get_all_product_stock",
                []
            );
            this._negStockState.stockData = data || {};
            this._negStockState.loaded = true;
        } catch (e) {
            console.error("[NegStock] Failed to load stock data:", e);
        }
    },

    /**
     * Public method: can be called from anywhere to force a refresh.
     */
    async refreshNegStock() {
        await this._loadStockData();
        this._applyStockBadges();
    },

    _applyStockBadges() {
        const settings = this._negStockState.settings;
        if (!settings || !settings.enabled || !settings.pos_enabled ||
            !settings.show_in_pos) {
            return;
        }

        const stockData = this._negStockState.stockData;
        const threshold = settings.threshold || 0;
        const hideOOS = settings.hide_out_of_stock || false;

        // Odoo 18: product cards are <article> elements with
        // class "product" and data-product-id attribute
        const productCards = document.querySelectorAll(
            "article.product[data-product-id]"
        );

        productCards.forEach((card) => {
            let productId = null;

            // Primary: use data-product-id attribute (Odoo 18 standard)
            if (card.dataset && card.dataset.productId) {
                productId = parseInt(card.dataset.productId);
            }

            // Fallback: try OWL component props
            if (!productId && card.__owl__ && card.__owl__.component &&
                card.__owl__.component.props &&
                card.__owl__.component.props.product) {
                productId = card.__owl__.component.props.product.id;
            }

            // Fallback 2: try productId prop directly
            if (!productId && card.__owl__ && card.__owl__.component &&
                card.__owl__.component.props &&
                card.__owl__.component.props.productId) {
                productId = parseInt(card.__owl__.component.props.productId);
            }

            if (!productId) return;

            // Remove existing badge
            const existing = card.querySelector(".neg-stock-badge");
            if (existing) existing.remove();

            // Get stock quantity
            const qty = stockData[productId];

            // Only show badges for storable products that have stock data
            if (qty === undefined || qty === null) return;

            const roundedQty = Math.floor(qty * 10) / 10; // 1 decimal

            // Auto-hide out-of-stock
            if (hideOOS && roundedQty <= 0) {
                card.classList.add("neg-stock-hidden");
                return;
            } else {
                card.classList.remove("neg-stock-hidden");
            }

            // Determine badge color
            let badgeClass = "neg-stock-badge-green";
            if (roundedQty <= 0) {
                badgeClass = "neg-stock-badge-red";
            } else if (roundedQty <= threshold) {
                badgeClass = "neg-stock-badge-yellow";
            }

            // Create and inject badge
            const badge = document.createElement("div");
            badge.className = "neg-stock-badge " + badgeClass;
            badge.textContent = roundedQty;

            // Ensure card has relative positioning
            card.style.position = "relative";
            card.appendChild(badge);
        });
    },
});
