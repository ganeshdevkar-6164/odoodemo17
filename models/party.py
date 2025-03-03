from odoo import models, fields, api, _ 
from odoo.exceptions import UserError, ValidationError
import requests



class Party(models.Model):
    _name = 'vighnahar_agro.party'
    _description = 'Party'
    
    name = fields.Char(string='Party Name', required=True)
    image = fields.Binary(string='Party Image')
    registration_date = fields.Date(string = "Registration Date", default=fields.Date.today)
    documents = fields.Binary(string = "Document")
    documents_name = fields.Char(string = "Document Name")
    is_supplier = fields.Boolean(string='Supplier')
    is_customer = fields.Boolean(string='Customer')
    party_type = fields.Selection([
        ('farmer','Farmer'),
        ('trader','Trader'),
        ('labor','Labor')
        ], string='Party Type',required=True, default = 'farmer')
    
    # Personal Information
    address = fields.Char(string='Address', required=True)
    city = fields.Char(string='City', required=True)
    state_id = fields.Many2one('res.country.state', default=lambda self: self.env['res.country.state'].search([('name', '=', 'Maharashtra'), ('country_id.code', '=', 'IN')], limit=1))
    zip_code = fields.Char(string='Zip/Postal Code')
    country_id = fields.Many2one('res.country', string='Country', default=lambda self: self.env['res.country'].search([('code', '=', 'IN')], limit=1))
    contact = fields.Char(string='Contact', required=True)
    optional_contact = fields.Char(string='Optional Contact')
    email = fields.Char(string='Email')
    website = fields.Char(string='Website')
    description = fields.Text(string='Description')
    
    
    #Accounting information
    

    
    
    
    #invoiceing
    bank_account_ids = fields.One2many('vighnahar_agro.bank_account', 'party_id', string='Bank Account')
    
    
    #Farms Details Id 
    farm_details_ids = fields.One2many('vighnahar_agro.farm_details', 'party_id', string='Farm Details')

   
#Farm Details Model 
class FarmDetails(models.Model):
    _name = 'vighnahar_agro.farm_details'
    _description = 'Farm Details'

    party_id = fields.Many2one('vighnahar_agro.party', string='Party')
    name = fields.Char(string='Village')
    farm_location = fields.Char(string='Farm Location')
    quantity = fields.Float(string='Farm Area')
    uom_id = fields.Many2one('vighnahar_agro.uom', string='UOM'
                             ,domain="[('category_id', '=', uom_category_id)]")
    converted_quantity = fields.Float(string='Converted Quantity', digits=(16, 4), compute='_compute_converted_quantity', store=True)
    converted_uom_id = fields.Many2one('vighnahar_agro.uom', string='Converted UOM', compute='_compute_converted_quantity', store=True) 
    uom_category_id = fields.Many2one('vighnahar_agro.uom_category', string='UOM Category'
                                      ,default=lambda self: self.env['vighnahar_agro.uom_category'].search([('name', '=', 'Farm Size')], limit=1)) 
    coordinates = fields.Char(string='Coordinates')
    view_location = fields.Char(string='View Location', compute='_compute_view_location', store=True)

    @api.depends('coordinates')
    def _compute_view_location(self):
        for record in self:
            if record.coordinates:
                record.view_location = f"https://www.google.com/maps?q={record.coordinates}"
            else:
                record.view_location = ''
    
    
    
    @api.depends('quantity', 'uom_id', 'uom_category_id')
    def _compute_converted_quantity(self):
        for line in self:
            if line.uom_category_id:
                base_uom = self.env['vighnahar_agro.uom'].search([('category_id', '=', line.uom_category_id.id), ('factor', '=', 1)], limit=1)
                if line.uom_id and base_uom:
                    line.converted_quantity = line.quantity * line.uom_id.factor / base_uom.factor
                    line.converted_uom_id = base_uom.id
                else:
                    line.converted_quantity = line.quantity
                    line.converted_uom_id = base_uom.id if base_uom else False
            else:
                line.converted_quantity = line.quantity
                line.converted_uom_id = False
    
    