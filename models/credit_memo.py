# from odoo import models, fields, api, _

# from odoo.exceptions import UserError

# class CreditMemo(models.Model):
#     _name = 'vighnahar_agro.credit_memo'

#     _description = 'Credit Memo'
    
              
#     name = fields.Char(string="Reference")
#     party_id = fields.Many2one('vighnahar_agro.party', string="Party", required=True)
#     date = fields.Date(string = "Date", default=fields.Date.today)
#     total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)
#     state = fields.Selection([
#         ('draft', 'Draft'),
#         ('credit', 'Credit'),
#         ('sales_order', 'Sales Order'),
#         ('cancel', 'Cancel')
#     ], string='Status', default='draft', required=True)
    

#     # code to calculate total amount of all supply lines
#     @api.depends('supply_line_ids.total')
#     def _compute_total_amount(self):
#         for record in self:
#             record.total_amount = sum(line.total for line in record.supply_line_ids)
    
    
#     # supply lines 
#     supply_line_ids = fields.One2many('vighnahar_agro.supply_line', 'credit_memo_id', string='Supply Lines')
    
    
#     #buttons
    
#     # confirm order
#     def action_confirm_order(self):
#         for rec in self:
#             rec.state = 'sales_order'
            
#     # credit       
#     def action_credit(self):
#         for rec in self:
#             rec.state = 'credit'

#     # cancel
#     def action_cancel(self):
#         for rec in self:
#             rec.state = 'cancel'




# class SupplyLine(models.Model):
#     _name = 'vighnahar_agro.supply_line'
#     _description = 'Resources Supply Line'
    
#     credit_memo_id = fields.Many2one('vighnahar_agro.credit_memo', string='Credit Memo')
#     product_id = fields.Many2one('vighnahar_agro.product', string='Product')
#     quantity = fields.Float(string='Quantity')
#     price = fields.Float(string="Unit Price", related='product_id.sales_price', store=True)
#     total = fields.Float(string='Total', compute='_compute_total', store=True)
    
#     @api.depends('quantity', 'price')
#     def _compute_total(self):
#         for record in self:
#             record.total = record.quantity * record.price
    
    
    