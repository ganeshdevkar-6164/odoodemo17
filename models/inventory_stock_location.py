from odoo import models, fields, api

class Warehouse(models.Model):
    _name = 'vighnahar_agro.warehouse'
    _description = 'Vighnahar Agro Warehouse'

    name = fields.Char(string='Warehouse Name', required=True)
    short_name = fields.Char(string='Short Name', required=True)
    address = fields.Text(string='Address')
    company = fields.Many2one('res.company', string='Company')
    