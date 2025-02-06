# -*- coding: utf-8 -*-
from odoo import models, fields

class CustomerRegistration(models.Model):
    _name = 'customer.registration'
    _description = 'Customer Registration'

    name = fields.Char(string='Customer Name', required=True)
    email = fields.Char(string='Email Address')
    phone = fields.Char(string='Phone Number')
    address = fields.Text(string='Address')
    registration_date = fields.Date(string='Registration Date', default=fields.Date.today)

    # Add more custom fields related to customer preferences, order history, etc.