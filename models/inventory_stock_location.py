from odoo import models, fields

class InventoryWarehouse(models.Model):
    _name = 'custom.inventory.warehouse'
    _description = 'Custom Warehouse'

    name = fields.Char(string="Warehouse Name", required=True)
    code = fields.Char(string="Warehouse Code", required=True)
    address = fields.Text(string="Address")  # New field for warehouse address
    description = fields.Text(string="Description")  # New field for warehouse description
    # product_ids = fields.One2many('custom.product', 'wh_loc_id', string="Products")  # Products linked to warehouse


class SubInventoryWarehouse(models.Model):
    _name = 'sub.inventory.warehouse'
    _description = 'Sub Inventory Warehouse'

    name = fields.Char(string="Sub Inventory Warehouse Name", required=True)
    code = fields.Char(string="Warehouse Code", required=True)
    address = fields.Text(string="Address")
    description = fields.Text(string="Description")

    # transfer_line_ids = fields.One2many('custom.inventory.transfer', 'destination_warehouse_id', string="Product Transfers")
