/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    /**
     * With badge login the Odoo user is whoever opened the session, which may
     * be a supervisor who never touched this sale. The employee is the person
     * who actually served the customer, so their policy governs.
     *
     * An employee with no policy of their own falls through to the base
     * behaviour, which reads it from the linked Odoo user.
     */
    get eaglepubPolicySource() {
        return this.employee_id?.eaglepub_pos_policy_id || super.eaglepubPolicySource;
    },
});

patch(PosStore.prototype, {
    /**
     * Under pos_hr this.cashier is already an hr.employee, so the base getter
     * would find the field only because the bridge loads it onto the employee.
     * Spelling the fallback out here keeps it working for an employee who has
     * no policy but whose linked user does.
     */
    get eaglepubPolicy() {
        const cashier = this.cashier;
        if (cashier?.eaglepub_pos_policy_id) {
            return cashier.eaglepub_pos_policy_id;
        }
        return cashier?.user_id?.eaglepub_pos_policy_id || super.eaglepubPolicy;
    },
});
