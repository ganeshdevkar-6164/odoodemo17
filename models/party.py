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
    party_type = fields.Selection([('farmer','Farmer'),('trader','Trader')], string='Party Type', default = 'farmer')
    
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
    

    
    
    
    
    
    
    #Farms Details Id 
    farm_details_ids = fields.One2many('vighnahar_agro.farm_details', 'party_id', string='Farm Details')

   
#Farm Details Model 
class FarmDetails(models.Model):
    _name = 'vighnahar_agro.farm_details'
    _description = 'Farm Details'

    party_id = fields.Many2one('vighnahar_agro.party', string='Party')
    name = fields.Char(string='Village')
    farm_location = fields.Char(string='Farm Location')
    farm_area = fields.Float(string='Farm Area(acer)')
    primary_uom = fields.Many2one('vighnahar_agro.uom', string='Primary UOM', default=lambda self: self.env['vighnahar_agro.uom'].search([('name', '=', 'Acer')], limit=1))
    farm_area1 = fields.Float(string='Farm Area(Ha)')
    secondary_uom = fields.Many2one('vighnahar_agro.uom', string='Secondary UOM', default=lambda self: self.env['vighnahar_agro.uom'].search([('name', '=', 'Hectare')], limit=1))
    farm_area2 = fields.Float(string='Farm Area(gunta)')
    conversion_uom = fields.Many2one('vighnahar_agro.uom', string='Convertion UOM', default=lambda self: self.env['vighnahar_agro.uom'].search([('name', '=', 'Guntha')], limit=1))
    coordinates = fields.Char(string='Coordinates')
    view_location = fields.Char(string='View Location', compute='_compute_view_location', store=True)

    @api.depends('coordinates')
    def _compute_view_location(self):
        for record in self:
            if record.coordinates:
                record.view_location = f"https://www.google.com/maps?q={record.coordinates}"
            else:
                record.view_location = ''
    

    @api.onchange('farm_area')
    def _onchange_farm_area(self):
        if self.farm_area:
            # Convert Acre to Hectare
            self.farm_area1 = self.farm_area * 0.4047
            # Convert Acre to Gunta
            self.farm_area2 = self.farm_area * 40
        else:
            self.farm_area1 = 0.0
            self.farm_area2 = 0.0

    @api.onchange('farm_area1')
    def _onchange_farm_area1(self):
        if self.farm_area1:
            # Convert Hectare to Acre
            self.farm_area = self.farm_area1 * 2.471
            # Convert Hectare to Gunta
            self.farm_area2 = self.farm_area1 * 100
        else:
            self.farm_area = 0.0
            self.farm_area2 = 0.0
            
            
    @api.onchange('farm_area2')
    def _onchange_farm_area2(self):
        if self.farm_area2:
            # Convert Gunta to Acre
            self.farm_area = self.farm_area2 * 0.0247
            # Convert Gunta to Hectare
            self.farm_area1 = self.farm_area2 * 0.01
        else:
            self.farm_area = 0.0
            self.farm_area1 = 0.0