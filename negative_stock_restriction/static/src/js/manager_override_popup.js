/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";

export class ManagerOverridePopup extends Component {
    static template = "negative_stock_restriction.ManagerOverridePopup";
    static components = { Dialog };
    static props = {
        title: { type: String, optional: true },
        issues: { type: Array, optional: true },
        close: { type: Function },
        getPayload: { type: Function, optional: true },
    };
    static defaultProps = {
        title: _t("Manager Override"),
        issues: [],
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            pin: "",
            error: "",
            loading: false,
        });
    }

    onPinInput(ev) {
        // Only allow digits, max 10 chars
        this.state.pin = ev.target.value.replace(/\D/g, "").slice(0, 10);
        this.state.error = "";
    }

    onKeyup(ev) {
        if (ev.key === "Enter") {
            this.verifyPin();
        }
    }

    async verifyPin() {
        if (!this.state.pin) {
            this.state.error = _t("Please enter a PIN");
            return;
        }

        this.state.loading = true;
        this.state.error = "";

        try {
            const result = await this.orm.call(
                "pos.session",
                "verify_manager_pin",
                [this.state.pin]
            );

            if (result.valid) {
                if (this.props.getPayload) {
                    this.props.getPayload(true);
                }
                this.props.close();
            } else if (!result.is_manager) {
                this.state.error = _t(
                    "You are not in the Manager Override group"
                );
            } else {
                this.state.error = _t("Incorrect PIN");
            }
        } catch (error) {
            console.error("PIN verify error:", error);
            this.state.error = _t("Verification failed");
        } finally {
            this.state.loading = false;
        }
    }

    cancel() {
        this.props.close();
    }
}
