from odoo import api, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _eaglepub_policy_for(self, order):
        """Prefer the employee who rang the order up.

        With badge login the Odoo user is whoever opened the session, which may
        be a supervisor who never touched this sale. The employee is the person
        who actually served the customer, so their policy is the one that counts.

        An employee with no policy of their own falls back to the base
        behaviour, which reads it from the linked Odoo user.
        """
        employee = self.env['hr.employee'].sudo().browse(order.get('employee_id'))
        if employee.exists() and employee.eaglepub_pos_policy_id:
            return employee.eaglepub_pos_policy_id
        return super()._eaglepub_policy_for(order)
