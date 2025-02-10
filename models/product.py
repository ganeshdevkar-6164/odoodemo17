from odoo import models, fields, api

class Product(models.Model):
    _name = 'vighnahar_agro.product'
    _description = 'Product'
    
    
    name = fields.Char(string='Product Name', required=True)
    description = fields.Text(string='Description')
    image = fields.Binary(string='Product Image')
    can_be_sold = fields.Boolean(string='Can be Sold')
    can_be_purchased = fields.Boolean(string='Can be Purchased')
    is_service = fields.Boolean(string='Service')
    
    
    
    
    # for General Information
    product_type = fields.Selection([('consumable','Consumable'),
                                     ( 'service','Service'), 
                                     ('product','Storable Product')], string='Product Type',default = 'product', required=True)
    sales_price = fields.Float(string='Sales Price')
    cost_price = fields.Float(string='Cost Price')
    product_category_id = fields.Many2one('vighnahar_agro.product_category', string='Product Category')
    uom_id = fields.Many2one('vighnahar_agro.uom' , string = "Unit Of Measures")
    category_id = fields.Many2one('vighnahar_agro.uom_category', string='Category')
    define_date = fields.Date(string = "Product Define", default=fields.Date.today)
    
    
    
    # for Inventory
    route_buy = fields.Boolean(string='Buy')
    route_dropship = fields.Boolean(string='Dropship')
    weight = fields.Float(string='Weight')
    volume = fields.Float(string='Volume')
    weight_uom_id = fields.Many2one('vighnahar_agro.uom', string='Weight Unit of Measure')
    volume_uom_id = fields.Many2one('vighnahar_agro.uom', string='Volume Unit of Measure')
    tracking = fields.Selection([('none','No Tracking'),
                                ('serial','By Unique Serial Number'),
                                ('lot','By Lots'),
                                ('package','By Package')], string='Tracking', default = 'none')

    
    
    
    
    #for Attribute
    attribute_line_ids = fields.One2many('vighnahar_agro.attribute_line', 'product_id', string='Attribute Line')
    
    #for Purchase (Supplier Info Line)
    supplier_info_ids = fields.One2many('vighnahar_agro.supplier_info', 'product_id', string='Supplier Info')
    
    
   
   
   
   
    
class AttributeLine(models.Model):
    _name = 'vighnahar_agro.attribute_line'
    _description = 'Attribute Line'
    
    
    product_id = fields.Many2one('vighnahar_agro.product', string='Product')
    attributes_id = fields.Many2one('vighnahar_agro.attributes', string='Attributes')
    attributes_line_id = fields.Many2one('vighnahar_agro.attributes_line', string='Value')




class SupplierInfo(models.Model):
    _name = 'vighnahar_agro.supplier_info'
    _description = 'Supplier Info'
    
    
    product_id = fields.Many2one('vighnahar_agro.product', string='Product')
    party_id = fields.Many2one('vighnahar_agro.party', string='Vendor')
    price = fields.Float(string='Price')
    delay = fields.Integer(string='Delivery Lead Time')
    uom_id = fields.Many2one('vighnahar_agro.uom', string='Unit of Measure')
    min_qty = fields.Float(string='Minimal Quantity')
    company_id = fields.Many2one('res.company', string='Company')
    
    
    

    
    
