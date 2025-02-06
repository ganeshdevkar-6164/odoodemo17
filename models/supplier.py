# import logging
from odoo import models, fields
# from twilio.rest import Client  # Ensure Twilio SDK is installed and available

# Initialize logger
# _logger = logging.getLogger(__name__)

class SupplierType(models.Model):
    _name = 'supplier.type'
    _description = 'Supplier Type'

    name = fields.Char(string="Supplier Type Name", required=True)
    description = fields.Text(string="Description")  # Description of the supplier type
    created_on = fields.Datetime(string="Created On", default=fields.Datetime.now)  # Default to current datetime

class SupplierRegistration(models.Model):
    _name = 'supplier.registration'
    _description = 'Supplier Registration'

    name = fields.Char(string='Supplier Name', required=True)
    email = fields.Char(string='Email Address')
    phone = fields.Char(string='Phone Number')
    address = fields.Text(string='Address')
    registration_date = fields.Date(string='Registration Date', default=fields.Date.today)
    company_id = fields.Many2one('res.company', string="Company")

    # Supplier Type as Many2many relationship to 'supplier.type' model
    # supplier_type = fields.Many2many('supplier.type', string="Supplier Type", required=True)
    supplier_type = fields.Selection([
            ('farmer', 'Farmer'),
            ('customer', 'Customer'),
            ('trade_supplier', 'Trade Supplier')
        ], string="Supplier Type", required=True)
    state = fields.Selection([('draft', 'Draft'), ('register', 'Registered'), ('cancelled', 'Cancelled')], default='draft', string='Status')

    # Land details (One2many relation to the supplier.land model)
    land_ids = fields.One2many('supplier.land', 'supplier_id', string="Land Details")

    # Loan details (One2many relation to custom.resource.share)
    loan_ids = fields.One2many('custom.resource.share', 'supplier_id', string="Loans")

    # Document upload for farmer documents (like 7/12 or other documents)
    document_file = fields.Binary(string="Document File")
    document_type = fields.Selection([('7_12', '7/12'), ('other', 'Other')], string="Document Type", required=True)

    def action_confirm(self):
        """ This method is called to confirm the supplier registration. """
        
        # Update supplier state to 'register'
        self.write({'state': 'register'})
        
        # Prepare the message to send
        # message = Hi, %s. Your supplier registration is now confirmed and completed!' % self.name)

        # # Send WhatsApp message using Twilio (ensure this is active and properly configured)
        # try:
        #     self.send_whatsapp_message(self.phone, message)
        #     _logger.info("WhatsApp message sent successfully to %s", self.phone)
        # except Exception as e:
        #     _logger.error("Failed to send WhatsApp message to %s: %s", self.phone, str(e))

        # # After registration, simply return an action to show success confirmation or redirect to the supplier form
        # return {
        #     'type': 'ir.actions.act_window',
        #     'res_model': 'supplier.registration',
        #     'view_mode': 'form',
        #     'res_id': self.id,
        #     'target': 'current',  # This keeps the user on the current window/form
        # }

    # def send_whatsapp_message(self, phone_number, message):
    #     """ Function to send WhatsApp message using Twilio API """
    #     # Twilio credentials (replace with your actual credentials)
    #     account_sid = 'your_twilio_account_sid'  # Twilio Account SID
    #     auth_token = 'your_twilio_auth_token'  # Twilio Auth Token
        
    #     # Your Twilio WhatsApp number (sandbox or production)
    #     from_whatsapp = 'whatsapp:+14155238886'  # Twilio Sandbox number, replace with your own production number if applicable

    #     # Ensure the phone number is in the correct format (whatsapp:+<phone_number>)
    #     formatted_phone_number = f'whatsapp:{phone_number.strip()}'

    #     # Log message status
    #     _logger.info(f"Sending WhatsApp message to {formatted_phone_number} with message: {message}")

    #     # Initialize Twilio client
    #     client = Client(account_sid, auth_token)

    #     # Send the WhatsApp message
    #     message = client.messages.create(
    #         body=message,
    #         from_=from_whatsapp,
    #         to=formatted_phone_number  # Make sure phone number is in the proper format
    #     )

    #     if message.status == 'sent':
    #         _logger.info(f"WhatsApp message successfully sent to {formatted_phone_number}")
    #     else:
    #         _logger.error(f"Failed to send WhatsApp message to {formatted_phone_number}. Status: {message.status}")


class SupplierRegistrationLand(models.Model):
    _name = 'supplier.land'
    _description = 'Land Details for Supplier'

    supplier_id = fields.Many2one('supplier.registration', string="Supplier")
    category_id = fields.Many2one('custom.uom.category', string="Category", required=True,
                                  default=lambda self: self.env['custom.uom.category'].search([('name', '=', 'Area')], limit=1))
                                  # Default category set to 'Area' from custom.uom.category
    uom_id = fields.Many2one('custom.uom', string="Unit of Measurement", required=True, domain="[('category_id', '=', category_id)]")
    land_size = fields.Float(string="Land Size (Acres)")
    land_location = fields.Char(string="Land Location")
    land_type = fields.Selection([('irrigated', 'Irrigated'),
                                  ('non_irrigated', 'Non-Irrigated')], string="Land Type", required=True)
