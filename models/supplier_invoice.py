from odoo import models, fields, api, _ 
from odoo.exceptions import UserError, ValidationError


class SupplierInvoce(models.Model):
    _name = 'vighnahar_agro.supplier_invoice'
    _description = 'Supplier Invoice'
    
    name = fields.Char(string="Reference")
    description = fields.Text(string="Description")
    party_id = fields.Many2one('vighnahar_agro.party', string="Party", required=True,domain=[('is_supplier', '=', True)])
    date = fields.Date(string = "Date", default=fields.Date.today)
    invoice_type = fields.Selection([('standard','Standard'),('credit','Credit Memo'),('debit','Debit Memo'),('prepayment', 'Pre Payment')], string='Invoice Type', default = 'standard')
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
    
    
    # Supplier Invoice Line
    supplier_invoice_line_ids = fields.One2many('vighnahar_agro.supplier_invoice_line', 'invoice_id', string='Invoice Lines')
    
 
    
class SupplierInvoiceLine(models.Model):
    _name = 'vighnahar_agro.supplier_invoice_line'
    _description = 'Supplier Invoice Line'

    invoice_id = fields.Many2one('vighnahar_agro.supplier_invoice', string='Invoice')
    uom_category_id = fields.Many2one('vighnahar_agro.uom_category', string='UOM Category')
    product_category_id = fields.Many2one('vighnahar_agro.product_category', string='Product Category')
    product_id = fields.Many2one('vighnahar_agro.product', string='Product', domain="[('product_category_id', '=', product_category_id)]")
    quantity = fields.Float(string='Quantity', digits=(16, 4))
    uom_id = fields.Many2one('vighnahar_agro.uom', string='Unit of Measure', domain="[('category_id', '=', uom_category_id)]")
    price = fields.Float(string='Unit Price', related='product_id.cost_price', store=True)
    total = fields.Float(string='Total Price', compute='_compute_total', store=True)
    converted_quantity = fields.Float(string='Converted Quantity', digits=(16, 4), compute='_compute_converted_quantity', store=True)
    converted_uom_id = fields.Many2one('vighnahar_agro.uom', string='Converted UOM', compute='_compute_converted_quantity', store=True)

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


    @api.depends('converted_quantity', 'price')
    def _compute_total(self):
        for line in self:
            line.total = line.converted_quantity * line.price
    