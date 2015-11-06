# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Dave Lasley <dave@laslabs.com>
#    Copyright: 2015 LasLabs, Inc.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp import models, api
from openerp.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _authorize_form_get_tx_from_data(self, data):
        """
        Given a data dict coming from authorize, verify it and find the related
        transaction record. Create transaction record if one doesn't exist.
        """

        reference = data.get('x_invoice_num')
        trans_id = data.get('x_trans_id')
        fingerprint = data.get('x_MD5_Hash')

        if not reference or not trans_id or not fingerprint:
            error_msg = 'Authorize: received data with missing reference ' +\
                '(%s) or trans_id (%s) or fingerprint (%s)' % (
                    reference, trans_id, fingerprint
                )
            _logger.error(error_msg)
            raise ValidationError(error_msg)

        # Create a transaction on the spot if it is missing
        tx = self.search([('reference', '=', reference)])
        if not tx:
            order = self.env['sale.order'].search([
                ('name', '=', reference)
            ], limit=1)
            acquirer = self.env['payment.acquirer'].search([
                ('provider', '=', 'authorize'),
                ('company_id', '=', order.company_id.id)
            ], limit=1)
	    amount = data.get('x_amount')

            tx = self.create({
                'acquirer_id': acquirer.id,
                'type': 'form',
                'amount': amount,
                'currency_id': order.pricelist_id.currency_id.id,
                'partner_id': order.partner_id.id,
                'partner_country_id': order.partner_id.country_id.id,
                'reference': order.name,
                'sale_order_id': order.id,
                'state': 'draft',
            })

	    # Update order
	    order.payment_acquirer_id = acquirer
	    order.payment_tx_id = tx

	    # Create payment for transaction
	    payment_method = self.env['payment.method'].search([('name', '=', 'Back Office')], limit=1)
	    if payment_method:
	    	order.payment_method_id = payment_method
	    	order.automatic_payment(amount)

	    	# Set workflow
	    	order.onchange_payment_method_set_workflow()
	    	order.onchange_workflow_process_id()

        if not tx or len(tx) > 1:
            error_msg = 'Authorize: received data for reference %s' % (
                reference
            )
            if not tx:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
                
            _logger.error(error_msg)
            raise ValidationError(error_msg)

        return tx[0]
