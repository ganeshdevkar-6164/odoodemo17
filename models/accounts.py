from odoo import models, fields, api
from odoo.exceptions import ValidationError

class Account(models.Model):
    _name = 'vighnahar_agro.account'
    _description = 'Chart of Accounts'
    
    name = fields.Char(string="Account Name", required=True)
    description = fields.Char(string = "Description")
    code = fields.Char(string="Account Code", required=True, unique=True)
    account_type = fields.Selection([
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('income', 'Income'),
        ('equity', 'Equity'),
        ('expense', 'Expense'),
    ], string="Account Type", required=True)
    
    @api.depends('name','code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name =f"{rec.code} - {rec.name}"
    
    

class Journal(models.Model):
    _name = 'vighnahar_agro.journal'
    _description = 'Journals'

    name = fields.Char(string="Journal Name", required=True)
    code = fields.Char(string="Journal Code", required=True)
    type = fields.Selection([
        ('sale', 'Sales'),
        ('purchase', 'Purchase'),
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('misc', 'Miscellaneous'),
    ], string="Journal Type", required=True)
    account_id = fields.Many2one('vighnahar_agro.account', string="Default Account")
    
    @api.depends('name','code')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code} - {rec.name}"



class JournalEntry(models.Model):
    _name = 'vighnahar_agro.journal_entry'
    _description = 'Journal Entries'

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default="New")
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one('vighnahar_agro.journal', string="Journal", required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='draft', required=True)
    line_ids = fields.One2many('vighnahar_agro.journal_item', 'entry_id', string="Journal Items")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.journal_entry') or 'New'
        return super(JournalEntry, self).create(vals)

    @api.depends('line_ids.debit', 'line_ids.credit')
    def _compute_total_amounts(self):
        for rec in self:
            rec.total_debit = sum(rec.line_ids.mapped('debit'))
            rec.total_credit = sum(rec.line_ids.mapped('credit'))

    total_debit = fields.Float(string="Total Debit", compute="_compute_total_amounts", store=True)
    total_credit = fields.Float(string="Total Credit", compute="_compute_total_amounts", store=True)

    def post_entry(self):
        for rec in self:
            if rec.total_debit != rec.total_credit:
                raise ValidationError("Total debit and credit must be equal before posting.")
            rec.state = 'posted'

    def cancel_entry(self):
        self.state = 'cancelled'


class JournalItem(models.Model):
    _name = 'vighnahar_agro.journal_item'
    _description = 'Journal Items'

    entry_id = fields.Many2one('vighnahar_agro.journal_entry', string="Journal Entry", required=True, ondelete="cascade")
    account_id = fields.Many2one('vighnahar_agro.account', string="Account", required=True)
    partner_id = fields.Many2one('vighnahar_agro.party', string="Partner")
    debit = fields.Float(string="Debit", default=0.0)
    credit = fields.Float(string="Credit", default=0.0)
    date = fields.Date(string="Date", related="entry_id.date", store=True)

    @api.constrains('debit', 'credit')
    def _check_debit_credit(self):
        for record in self:
            if record.debit > 0 and record.credit > 0:
                raise ValidationError("A journal item cannot have both debit and credit values.")
            if record.debit == 0 and record.credit == 0:
                raise ValidationError("A journal item must have either a debit or credit value.")

