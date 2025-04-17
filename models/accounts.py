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
        ('receivable', 'Receivable'),
        ('revenue', 'Revenue'),
        ('equity', 'Equity'),
        ('expense', 'Expense'),
        ('tax', 'Tax'),
    ], string="Account Type", required=True)
    # To hold the balance of the account (used for real-time balance calculation)
    balance = fields.Float(string='Balance', default=0.0, readonly=True)
    
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


class JournalItem(models.Model):
    _name = 'vighnahar_agro.journal_item'
    _description = 'Journal Item'

    entry_id = fields.Many2one('vighnahar_agro.journal_entry', string='Journal Entry', required=True, ondelete='cascade')
    account_id = fields.Many2one('vighnahar_agro.account', string='Account', required=True)
    party_id = fields.Many2one('vighnahar_agro.party', string='Party')

    debit = fields.Float(string='Debit', default=0.0)
    credit = fields.Float(string='Credit', default=0.0)
    date = fields.Date(string='Date', required=True)

    product_id = fields.Many2one('vighnahar_agro.product', string='Product', ondelete="cascade")
    supplier_invoice_id = fields.Many2one('vighnahar_agro.supplier_invoice', string='Supplier Invoice', ondelete="cascade")
    customer_invoice_id = fields.Many2one('vighnahar_agro.customer_invoice', string='Customer Invoice', ondelete="cascade")
    labor_payment_id = fields.Many2one('vighnahar_agro.labor_payment', string='Labor Payment', ondelete="cascade")
    tax_id = fields.Many2one('vighnahar_agro.account_tax', string='Tax', ondelete="cascade")

    @api.constrains('debit', 'credit')
    def _check_debit_credit(self):
        for line in self:
            if line.debit < 0.0 or line.credit < 0.0:
                raise ValidationError("Debit and Credit values must be positive.")
            if line.debit > 0.0 and line.credit > 0.0:
                raise ValidationError("A journal item cannot have both debit and credit values greater than zero.")


class JournalEntry(models.Model):
    _name = 'vighnahar_agro.journal_entry'
    _description = 'Journal Entry'

    name = fields.Char(string='Entry Reference', required=True, copy=False, readonly=True, default='New')
    date = fields.Datetime(string='Date', required=True)
    journal_id = fields.Many2one('vighnahar_agro.journal', string='Journal', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], string='State', default='draft')

    journal_item_ids = fields.One2many('vighnahar_agro.journal_item', 'entry_id', string="Journal Items", ondelete="cascade")

    party_id = fields.Many2one('vighnahar_agro.party', string='Party/Supplier')
    total_amount = fields.Float(string='Total Amount')

    supplier_invoice_id = fields.Many2one("vighnahar_agro.supplier_invoice", string="Supplier Invoice", ondelete="cascade")
    customer_invoice_id = fields.Many2one("vighnahar_agro.customer_invoice", string="Customer Invoice", ondelete="cascade")
    labor_payment_id = fields.Many2one('vighnahar_agro.labor_payment', string='Labor Payment', ondelete="cascade")

    total_amount_signed = fields.Float(string='Total Amount Signed', compute='_compute_total_amount_signed', store=True)

    
    @api.depends('journal_id', 'total_amount')
    def _compute_total_amount_signed(self):
        for rec in self:
            if rec.journal_id.type == 'purchase':  # Vendor Bill (Purchase)
                rec.total_amount_signed = -rec.total_amount  # Make the amount negative
            elif rec.journal_id.type == 'sale':  # Customer Invoice (Sale)
                rec.total_amount_signed = rec.total_amount  # Keep the amount positive
            else:
                rec.total_amount_signed = rec.total_amount  # Default case, if it's neither purchase nor sale
                
    def action_open_related_invoice(self):
        """ Open the related Supplier Invoice if found by matching name """
        self.ensure_one()
        supplier_invoice = self.env['vighnahar_agro.supplier_invoice'].search([('name', '=', self.name)], limit=1)
        
        if supplier_invoice:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Supplier Invoice',
                'res_model': 'vighnahar_agro.supplier_invoice',
                'view_mode': 'form',
                'res_id': supplier_invoice.id,
                'target': 'current',
            }
            
        customer_invoice = self.env['vighnahar_agro.customer_invoice'].search([('name', '=', self.name)], limit=1)
        
        if customer_invoice:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Customer Invoice',
                'res_model': 'vighnahar_agro.customer_invoice',
                'view_mode': 'form',
                'res_id': customer_invoice.id,
                'target': 'current',
            }
        
        labor_payment = self.env['vighnahar_agro.labor_payment'].search([('name', '=', self.name)], limit=1)

        if labor_payment:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Labor Payment',
                'res_model': 'vighnahar_agro.labor_payment',
                'view_mode': 'form',
                'res_id': labor_payment.id,
                'target': 'current',
            }
        
        return {'type': 'ir.actions.act_window_close'}  # Close if not found
        
        
    
    # To calculate the total debit and credit of the journal entry
    @api.depends('journal_item_ids.debit', 'journal_item_ids.credit')
    def _compute_total_debit_credit(self):
        for entry in self:
            total_debit = sum(line.debit for line in entry.journal_item_ids)
            total_credit = sum(line.credit for line in entry.journal_item_ids)
            entry.total_debit = total_debit
            entry.total_credit = total_credit

    total_debit = fields.Float(string='Total Debit', compute='_compute_total_debit_credit', store=True)
    total_credit = fields.Float(string='Total Credit', compute='_compute_total_debit_credit', store=True)
                
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.journal_entry') or 'New'
        return super(JournalEntry, self).create(vals)

    def post_entry(self):
        """Post the journal entry and update the accounts accordingly."""
        for entry in self:
            if entry.state == 'draft':
                entry.state = 'posted'
                for line in entry.journal_item_ids:
                    # Update the account balance for each journal item (debit and credit)
                    if line.debit > 0.0:
                        line.account_id.balance += line.debit
                    if line.credit > 0.0:
                        line.account_id.balance -= line.credit
                return True
            else:
                raise ValidationError("The journal entry has already been posted.")