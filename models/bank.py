from odoo import models, fields, api
import re
import base64
import qrcode
from io import BytesIO

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
    ifsc_code = fields.Char(string='IFSC Code')
    branch = fields.Char(string='Branch')
    upi_id = fields.Char(string='UPI ID')
  
    # Computed field for storing the UPI Payment QR Code
    qr_code_image = fields.Image(string="UPI Payment QR Code", compute="_generate_upi_payment_qr_code", store=True)

    @api.depends('upi_id')
    def _generate_upi_payment_qr_code(self):
        for record in self:
            if record.upi_id:
                # Construct UPI URI for payment using just the UPI ID
                upi_uri = f"upi://pay?pa={record.upi_id}"

                # Generate QR code based on the constructed UPI URI
                qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
                qr.add_data(upi_uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                # Convert the image to base64 to store in the image field
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                qr_code_image_base64 = base64.b64encode(buffer.getvalue())
                buffer.close()

                # Set the base64-encoded QR code image
                record.qr_code_image = qr_code_image_base64
            else:
                record.qr_code_image = False
    
    
    
    
    @api.depends('name', 'banks_id')
    def _compute_display_name(self):
        for record in self:
            bank_name = record.banks_id.name if record.banks_id else "No Bank"
            record.display_name = f"{record.name} - {bank_name}"
            
    
    

            
 