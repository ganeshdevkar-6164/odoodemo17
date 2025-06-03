from odoo import models, fields, api

class Product(models.Model):
    _name = 'vighnahar_agro.product'
    _description = 'Product'
    
    
    name = fields.Char(string='Product Name', required=True)
    description = fields.Text(string='Description')
    image = fields.Image(string="Product Image", max_width=1024, max_height=1024)
    can_be_sold = fields.Boolean(string='Can be Sold')
    can_be_purchased = fields.Boolean(string='Can be Purchased')
    
    
    
    
    
    
    # for General Information
    product_type = fields.Selection([('consumable','Consumable'),
                                     ( 'service','Service'), 
                                     ('product','Storable Product')], string='Product Type',default = 'product', required=True)
    sales_price = fields.Float(string='Sales Price', currency_field='currency_id')
    cost_price = fields.Float(string='Cost Price', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id.id
    )
    product_category_id = fields.Many2one('vighnahar_agro.product_category', string='Product Category')
    category_id = fields.Many2one('vighnahar_agro.uom_category', string='Category')
    uom_id = fields.Many2one('vighnahar_agro.uom' , string = "Unit Of Measures", domain="[('category_id', '=', category_id)]")
    
    define_date = fields.Date(string = "Product Define", default=fields.Date.today)
    
    
    #On Hand Quantity And Uom In Product Logic
    quantity = fields.Float(string="On-Hand Quantity", compute="_compute_quantity", store=False)
    unit_of_measure_id = fields.Many2one('vighnahar_agro.uom', string="Unit of Measure")
    
    @api.depends('product_category_id')
    def _compute_quantity(self):
        for product in self:
            inventory = self.env['vighnahar_agro.inventory_line'].search([
                ('product_id', '=', product.id)
            ])
            total_quantity = sum(inventory.mapped('quantity'))
            product.quantity = total_quantity
            
            # Assuming you want to display the first available unit of measure
            if inventory:
                product.unit_of_measure_id = inventory[0].uom_id
            else:
                product.unit_of_measure_id = False
    
    
    
    
    # for Inventory
    route_buy = fields.Boolean(string='Buy')
    route_dropship = fields.Boolean(string='Dropship')
    weight = fields.Float(string='Weight')
    volume = fields.Float(string='Volume')
    weight_uom_id = fields.Many2one('vighnahar_agro.uom', string='Weight Unit of Measure')
    volume_uom_id = fields.Many2one('vighnahar_agro.uom', string='Volume Unit of Measure')
    tracking = fields.Selection([('none','No Tracking'),
                                ('serial','By Unique Serial Number'),
                                ('lot','By Lots')], string='Tracking', default = 'none')

    
    
    
    
    #for Attribute
    attribute_line_ids = fields.One2many('vighnahar_agro.attribute_line', 'product_id', string='Attribute Line')
    
    #for Purchase (Supplier Info Line)
    supplier_info_ids = fields.One2many('vighnahar_agro.supplier_info', 'product_id', string='Supplier Info')
    
    #for Sales (Customer Info)
    # Optional Products (Upsell & Cross-Sell)
    optional_product_ids = fields.Many2many(
        'vighnahar_agro.product',
        'vighnahar_agro_product_optional_rel',
        'product_id', 'optional_product_id',
        string='Optional Products',
        help="Recommended when adding to cart."
    )
   
    
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