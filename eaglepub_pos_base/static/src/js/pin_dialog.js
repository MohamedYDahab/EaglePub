/** @odoo-module */

import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";

/**
 * Asks for the manager PIN at the till.
 *
 * Returns the typed PIN through getPayload; it is the caller's job to have the
 * server check it. Nothing here knows what the correct PIN is.
 */
export class ManagerPinDialog extends Component {
    static template = "eaglepub_pos_base.ManagerPinDialog";
    static components = { Dialog };
    static props = {
        reason: { type: String, optional: true },
        close: Function,
        getPayload: { type: Function, optional: true },
    };
    static defaultProps = { reason: "" };

    setup() {
        this.state = useState({ pin: "" });
    }

    get title() {
        return _t("Manager Authorisation");
    }

    press(digit) {
        this.state.pin += digit;
    }

    backspace() {
        this.state.pin = this.state.pin.slice(0, -1);
    }

    clear() {
        this.state.pin = "";
    }

    confirm() {
        if (!this.state.pin) {
            return;
        }
        this.props.getPayload?.(this.state.pin);
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}
