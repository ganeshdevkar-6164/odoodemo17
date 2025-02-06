from odoo import models, fields, api
from odoo.exceptions import UserError

class InventoryTransfer(models.Model):
    _name = 'custom.inventory.transfer'
    _description = 'Inventory Transfer from Physical Inventory to Sub Inventory'

    name = fields.Char(string="Transfer Reference", required=True, copy=False, readonly=True, default='New')
    source_warehouse_id = fields.Many2one('custom.inventory.warehouse', string="Source Warehouse", required=True)
    destination_warehouse_id = fields.Many2one('sub.inventory.warehouse', string="Destination Warehouse", required=True)
    transfer_date = fields.Datetime(string="Transfer Date", default=fields.Datetime.now)
    transfer_line_ids = fields.One2many('custom.inventory.transfer.line', 'transfer_id', string="Transfer Lines")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft')

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].next_by_code('inventory.transfer.custom.sequence')
        return super().create(vals)

    def confirm_transfer(self):
        """Confirm the transfer of products from physical to sub inventory"""
        for line in self.transfer_line_ids:
            # Find the source inventory (CustomPhysicalInventory) record
            source_inventory = self.env['custom.physical.inventory'].search([
                ('product_id', '=', line.product_id.id),
                ('wh_loc_id', '=', self.source_warehouse_id.id)
            ], limit=1)

            # Validate that we have enough quantity in the source inventory
            if not source_inventory or source_inventory.quantity < line.quantity:
                raise UserError("Not enough stock in the source warehouse to transfer.")

            # Deduct the quantity from the source inventory (CustomPhysicalInventory)
            source_inventory.quantity -= line.quantity

            # Find or create the destination inventory (SubInventory) record
            destination_inventory = self.env['sub.inventory'].search([
                ('product_id', '=', line.product_id.id),
                ('warehouse_id', '=', self.destination_warehouse_id.id)
            ], limit=1)

            if destination_inventory:
                # Add the quantity to the destination inventory (SubInventory)
                destination_inventory.quantity += line.quantity
            else:
                # Create a new SubInventory record if it doesn't exist
                self.env['sub.inventory'].create({
                    'product_id': line.product_id.id,
                    'warehouse_id': self.destination_warehouse_id.id,
                    'quantity': line.quantity
                })

        # Transition the state to "confirmed"
        self.state = 'confirmed'


class InventoryTransferLine(models.Model):
    _name = 'custom.inventory.transfer.line'
    _description = 'Inventory Transfer Line'

    transfer_id = fields.Many2one('custom.inventory.transfer', string="Transfer Reference", required=True)
    product_category_id = fields.Many2one('custom.product.category', string="Product Category", required=True)
    product_id = fields.Many2one('custom.product', string='Product', required=True, domain="[('product_category_id','=',product_category_id)]")    
    quantity = fields.Float('Quantity', required=True)
    uom_id = fields.Many2one('custom.uom', string='UOM', related='product_id.uom_id', store=True)
