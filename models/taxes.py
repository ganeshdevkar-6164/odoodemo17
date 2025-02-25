from odoo import models, fields

class Tax(models.Model):
    _name = 'vighnahar_agro.account_tax'
    _description = 'Account Tax'

    name = fields.Char(string="Tax Name", required=True)
    description = fields.Char(string="Description")
    amount = fields.Float(string="Tax Amount (%)", required=True, help="Tax percentage")
    type_tax_use = fields.Selection(
        [('sale', 'Sales'), ('purchase', 'Purchases')],
        string="Tax Scope",
        required=True,
        default='sale',
        help="Define if this tax is used for sales or purchases."
    )
    price_include = fields.Boolean(string="Included in Price", default=False, help="Indicates if the tax is included in the product price.")
    active = fields.Boolean(string="Active", default=True, help="If unchecked, this tax will not be available for use.")
