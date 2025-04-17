from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64
from io import BytesIO
import qrcode

class LaborPayment(models.Model):
    _name = 'vighnahar_agro.labor_payment'
    _description = 'Labor Payment'
    _order = "id desc"

    name = fields.Char(string="Payment Reference", required=True, copy=False, readonly=True, index=True, default='New')
    party_id = fields.Many2one(
        'vighnahar_agro.party', 
        string="Labor", 
        domain="[('party_type', '=', 'labor')]",  # Show only laborers
        required=True
    )
    date = fields.Date(string='Payment Date', default=fields.Date.today)
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('cheque', 'Cheque'),
        ('online', 'Online')
    ], string="Payment Method", required=True, default='cash')
    state = fields.Selection([
    ('draft', 'Draft'),
    ('paid', 'Paid'),
    ('cancel', 'Cancelled')  # Add 'cancel' as a valid state
], string="Payment Status", default='draft')
    journal_id = fields.Many2one(
        'vighnahar_agro.journal', 
        string='Journal', 
        required=True, 
        domain=[('type', '=', 'purchase')],
        default=lambda self: self.env.ref('vighnahar_agro.journal_labor_payment', raise_if_not_found=False)
    )

    amount = fields.Float(string='Amount', required=True)
    bank_account_id = fields.Many2one('vighnahar_agro.bank_account', string = "Bank Account", domain="[('party_id', '=', party_id)]")
    
    
    
     # Computed field to generate QR code image for online payment
    qr_code_image = fields.Image(string="Payment QR Code", compute='_generate_qr_code', store=True)

    @api.depends('payment_method', 'bank_account_id.upi_id', 'amount')
    def _generate_qr_code(self):
        for rec in self:
            if rec.payment_method == 'online' and rec.bank_account_id and rec.bank_account_id.upi_id:
                upi_uri = f"upi://pay?pa={rec.bank_account_id.upi_id}&am={rec.amount}&cu=INR"
                qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
                qr.add_data(upi_uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                rec.qr_code_image = base64.b64encode(buffer.getvalue())
                buffer.close()
            else:
                rec.qr_code_image = False
                
    # Generate unique sequence number    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('vighnahar_agro.labor_payment') or 'New'
        return super(LaborPayment, self).create(vals)
    
    
    @api.onchange('party_id', 'payment_method')
    def _onchange_party_payment_method(self):
        """ Automatically set bank_account_id when party_id is selected and payment_method is 'bank' """
        if self.party_id and self.payment_method in ('bank', 'online'):
            # If the party has bank accounts, select the first one
            if self.party_id.bank_account_ids:
                self.bank_account_id = self.party_id.bank_account_ids[:1].id
            else:
                self.bank_account_id = False  # Reset if no bank account exists
        else:
            self.bank_account_id = False  # Reset if payment method is not 'bank'

    def action_pay(self):
        for rec in self:
            if rec.state == 'paid':
                raise ValidationError("This payment is already processed.")
            
            # Ensure there is a journal selected
            if not rec.journal_id:
                raise ValidationError("Please select a journal for this payment.")

            # For online or bank payment, open a wizard for further details.
            if rec.payment_method in ('online', 'bank'):
                if rec.payment_method == 'online':
                    if not rec.bank_account_id or not rec.bank_account_id.upi_id:
                        raise ValidationError("Online payment requires a bank account with a UPI ID.")
                    return {
                        'name': 'UPI Payment QR Code',
                        'type': 'ir.actions.act_window',
                        'res_model': 'vighnahar_agro.labor_payment_qr_wizard',
                        'view_mode': 'form',
                        'view_id': self.env.ref('vighnahar_agro.view_labor_payment_qr_wizard_form').id,
                        'target': 'new',
                        'context': {
                            'default_payment_id': rec.id,
                            'default_qr_code_image': rec.qr_code_image,
                            'default_amount': rec.amount,
                        }
                    }
                elif rec.payment_method == 'bank':
                    if not rec.bank_account_id:
                        raise ValidationError("Please select a bank account for bank payment.")
                    return {
                        'name': 'Bank Payment Details',
                        'type': 'ir.actions.act_window',
                        'res_model': 'vighnahar_agro.labor_payment_bank_wizard',
                        'view_mode': 'form',
                        'view_id': self.env.ref('vighnahar_agro.view_labor_payment_bank_wizard_form').id,
                        'target': 'new',
                        'context': {
                            'default_payment_id': rec.id,
                            'default_bank_name': rec.bank_account_id.banks_id.name,
                            'default_account_number': rec.bank_account_id.name,
                            'default_branch': rec.bank_account_id.branch,
                            'default_ifsc_code': rec.bank_account_id.ifsc_code,
                            'default_bank_holder_name': rec.bank_account_id.party_id.name,
                            'default_amount': rec.amount,
                        }
                    }

            # Define accounts
            labor_expense_account = self.env['vighnahar_agro.account'].search([('account_type', '=', 'expense')], limit=1)
            payment_account = rec.journal_id.account_id  # Cash/Bank account

            if not labor_expense_account:
                raise ValidationError("No expense account found. Please configure an expense account.")

            if not payment_account:
                raise ValidationError("No payment account found for the selected journal.")

            # Create Journal Entry
            journal_entry = self.env['vighnahar_agro.journal_entry'].create({
                'name': rec.name,  # Assign the Labor Payment name here
                'date': rec.date,
                'journal_id': rec.journal_id.id,
                'party_id': rec.party_id.id,
                'total_amount': rec.amount,
                'state': 'draft',  # Set to draft initially
                'labor_payment_id': rec.id  # Link Labor Payment to Journal Entry
            })

            # Create Journal Items (Debiting Labor Expense & Crediting Payment Account)
            self.env['vighnahar_agro.journal_item'].create([
                {
                    'entry_id': journal_entry.id,
                    'account_id': labor_expense_account.id,
                    'party_id': rec.party_id.id,
                    'debit': rec.amount,
                    'credit': 0.0,
                    'date': rec.date,
                },
                {
                    'entry_id': journal_entry.id,
                    'account_id': payment_account.id,
                    'debit': 0.0,
                    'credit': rec.amount,
                    'date': rec.date,
                }
            ])

            # Post the Journal Entry
            journal_entry.post_entry()

            # Mark payment as paid
            rec.state = 'paid'



class LaborPaymentQRCodeWizard(models.TransientModel):
    _name = 'vighnahar_agro.labor_payment_qr_wizard'
    _description = 'Labor Payment QR Code Wizard'

    payment_id = fields.Many2one('vighnahar_agro.labor_payment', string="Labor Payment")
    qr_code_image = fields.Image(string="Payment QR Code")
    amount = fields.Float(string="Amount")

    @api.model
    def default_get(self, fields):
        res = super(LaborPaymentQRCodeWizard, self).default_get(fields)
        if self.env.context.get('default_upi_link'):
            res['upi_link'] = self.env.context.get('default_upi_link')
        if self.env.context.get('default_qr_code_image'):
            res['qr_code_image'] = self.env.context.get('default_qr_code_image')
        if self.env.context.get('default_amount'):
            res['amount'] = self.env.context.get('default_amount')
        return res

    def action_done(self):
        self.payment_id.state = 'paid'
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        self.payment_id.state = 'cancel'
        return {'type': 'ir.actions.act_window_close'}


# Wizard for Bank Payment Details
class LaborPaymentBankWizard(models.TransientModel):
    _name = 'vighnahar_agro.labor_payment_bank_wizard'
    _description = 'Labor Payment Bank Wizard'

    payment_id = fields.Many2one('vighnahar_agro.labor_payment', string="Labor Payment")
    bank_name = fields.Char(string="Bank Name")
    account_number = fields.Char(string="Account Number")
    branch = fields.Char(string="Branch")
    ifsc_code = fields.Char(string="IFSC Code")
    bank_holder_name = fields.Char(string="Bank Holder Name")
    amount = fields.Float(string="Amount to Pay")

    @api.model
    def default_get(self, fields):
        res = super(LaborPaymentBankWizard, self).default_get(fields)
        if self.env.context.get('default_bank_name'):
            res['bank_name'] = self.env.context.get('default_bank_name')
        if self.env.context.get('default_account_number'):
            res['account_number'] = self.env.context.get('default_account_number')
        if self.env.context.get('default_branch'):
            res['branch'] = self.env.context.get('default_branch')
        if self.env.context.get('default_ifsc_code'):
            res['ifsc_code'] = self.env.context.get('default_ifsc_code')
        if self.env.context.get('default_bank_holder_name'):
            res['bank_holder_name'] = self.env.context.get('default_bank_holder_name')
        if self.env.context.get('default_amount'):
            res['amount'] = self.env.context.get('default_amount')
        return res

    def action_done(self):
        self.payment_id.state = 'paid'
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        self.payment_id.state = 'cancel'  # <-- Error occurs here
        return {'type': 'ir.actions.act_window_close'}