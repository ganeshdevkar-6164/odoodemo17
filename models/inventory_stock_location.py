from odoo import models, fields, api

class Warehouse(models.Model):
    _name = 'vighnahar_agro.warehouse'
    _description = 'Vighnahar Agro Warehouse'

    name = fields.Char(string='Warehouse Name', required=True)
    short_name = fields.Char(string='Short Name', required=True)
    address = fields.Text(string='Address')
    company = fields.Many2one('res.company', string='Company')
    


class PhysicalInventory(models.Model):
    _name = 'vighnahar_agro.physical_inventory'
    _description = 'Vighnahar Agro Inventory'
    
    
    warehouse_id = fields.Many2one('vighnahar_agro.warehouse', string = "Warehouse")
    inventory_line_ids = fields.One2many('vighnahar_agro.inventory_line', 'physical_inventory_id', string="Stock Lines")
    
    
class InventoryLine(models.Model):
    _name = 'vighnahar_agro.inventory_line'
    _description = 'Inventory Line'

    physical_inventory_id = fields.Many2one('vighnahar_agro.physical_inventory', string="Stock Location", ondelete='cascade')
    product_category_id = fields.Many2one('vighnahar_agro.product_category', string='Product Category')
    product_id = fields.Many2one('vighnahar_agro.product', string='Product')
    quantity = fields.Float(string='On Hand Quantity')
    uom_id = fields.Many2one('vighnahar_agro.uom', related='product_id.uom_id', string='UOM')