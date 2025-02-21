from odoo import models, fields, api

class Banks(models.Model):
    _name = 'vighnahar_agro.banks'
    _description = 'Banks'  
    
    name = fields.Char(string='Bank Name', required=True)
    code = fields.Char(string= 'Bank Identifier Code')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    address = fields.Char(string = 'Address')
    
    
class BankAccount(models.Model):
    _name = 'vighnahar_agro.bank_account'
    _description = 'Bank Account'  
    
    name = fields.Char(string='Account Number', required=True)
    banks_id = fields.Many2one('vighnahar_agro.banks', string = "Bank", required = True)
    party_id = fields.Many2one('vighnahar_agro.party', string='Account Holder')
    
    
    @api.depends('name', 'banks_id')
    def _compute_display_name(self):
        for record in self:
            bank_name = record.banks_id.name if record.banks_id else "No Bank"
            record.display_name = f"{record.name} - {bank_name}"
            
