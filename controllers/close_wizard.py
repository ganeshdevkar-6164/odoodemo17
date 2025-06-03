# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class PaymentWizardCloseController(http.Controller):

    @http.route('/vighnahar_agro/close_wizard', type='json', auth='user')
    def close_wizard(self):
        return {'type': 'ir.actions.act_window_close'}
