from odoo import models, fields, api

#Unit of Measure Category
class UoMCategory(models.Model):
    _name = 'vighnahar_agro.uom_category'
    _description = 'Unit of Measure Category'

    name = fields.Char(string='Category Name', required=True)
    uom_ids = fields.One2many('vighnahar_agro.uom', 'category_id', string='Units of Measure')

#unit of measure
class UoM(models.Model):
    _name = 'vighnahar_agro.uom'
    _description = 'Unit of Measure'

    name = fields.Char(string='Unit of Measure', required=True)
    category_id = fields.Many2one('vighnahar_agro.uom_category', string='Category', required=True)
    factor = fields.Float(string='Factor', required=True, digits=(16, 4), help="Factor to convert from this unit to the reference unit of the category")
    active = fields.Boolean(string='Active', default=True)
    


#Product Category
class ProductCategory(models.Model):
    _name = 'vighnahar_agro.product_category'
    _description = 'Product Category'  
    
    name = fields.Char(string='Category Name', required=True)
    define_date = fields.Datetime(string="Define Date", default=fields.Datetime.now)
    



    
    
#Attributes   
class Attributes(models.Model):
    _name = 'vighnahar_agro.attributes'
    _description = 'Attributes'
    
    name = fields.Char(string='Attribute Name', required=True)
    attributes_line_ids = fields.One2many('vighnahar_agro.attributes_line', 'attributes_id', string='Attribute Line')


#Attributes Line
class AttributesLine(models.Model):
    _name = 'vighnahar_agro.attributes_line'
    _description = 'Attributes Line'
    
    name = fields.Char(string='Value', required=True)
    attributes_id = fields.Many2one('vighnahar_agro.attributes', string='Attributes')
    is_custom = fields.Boolean(string='Is Custom Value')
    default_extra_price = fields.Float(string='Default Extra Price')
    


# class PaymentTerms(models.Model):
#     _name = 'vighnahar_agro.payment_terms'
#     _description = 'Payment Terms'  
    
#     name = fields.Char(string='Payment Terms', required=True)
#     define_date = fields.Datetime(string="Define Date", default=fields.Datetime.now)