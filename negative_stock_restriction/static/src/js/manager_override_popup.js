/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class ManagerOverridePopup extends AbstractAwaitablePopup {
    static template = "negative_stock_restriction.ManagerOverridePopup";
    static defaultProps = {
        title: _t("Manager Override / تجاوز المدير"),
        issues: [],
    };

    setup() {
        super.setup();
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
            this.state.error = _t("Please enter a PIN / الرجاء إدخال رمز");
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
                this.props.close({ confirmed: true, payload: { pin: this.state.pin } });
            } else if (!result.is_manager) {
                this.state.error = _t(
                    "You are not in the Manager Override group / لست في مجموعة تجاوز المدير"
                );
            } else {
                this.state.error = _t("Incorrect PIN / رمز غير صحيح");
            }
        } catch (error) {
            console.error("PIN verify error:", error);
            this.state.error = _t("Verification failed / فشل التحقق");
        } finally {
            this.state.loading = false;
        }
    }

    cancel() {
        this.props.close({ confirmed: false, payload: null });
    }
}
