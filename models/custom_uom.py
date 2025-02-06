from odoo import models, fields, api

class CustomUOMCategory(models.Model):
    _name = 'custom.uom.category'
    _description = 'Custom Unit of Measurement Category'

    name = fields.Char('Category Name', required=True)
    description = fields.Text('Description')  # Optional description for the category

class CustomUOM(models.Model):
    _name = 'custom.uom'
    _description = 'Custom Unit of Measurement'

    name = fields.Char('UOM Name', required=True)
    category_id = fields.Many2one('custom.uom.category', string="Category", required=True)  # Link to Custom UOM categories
    factor = fields.Float('Conversion Factor', default=1.0)  # Factor for conversions
    description = fields.Text('Description')  # Optional description of the UOM
