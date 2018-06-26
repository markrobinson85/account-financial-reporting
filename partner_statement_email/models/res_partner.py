# -*- coding: utf-8 -*-

import json
from lxml import etree
from datetime import datetime
from dateutil.relativedelta import relativedelta

from openerp import api, fields, models, _
from openerp.tools import float_is_zero, float_compare
from openerp.tools.misc import formatLang

from openerp.exceptions import UserError, RedirectWarning, ValidationError

import openerp.addons.decimal_precision as dp
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # @api.multi
    # def payslip_quicksend(self):
    #     payslip_ids = self.filtered(lambda l: l.employee_id.address_home_id.email is not False)
    #     if len(payslip_ids) == 0:
    #         raise UserError('The employee does not have an e-mail address on file.')
    #     for payslip in payslip_ids:
    #         mail_template = self.env.ref('payroll_base.email_template_payslip', False)
    #         mail_template.with_context(active_model='hr.payslip', active_ids=[payslip.id]).send_mail(payslip.id, force_send=True)

    @api.multi
    def action_partner_statement_send(self):
        """ Open a window to compose an email
        """
        self.ensure_one()
        # template = self.env.ref('account.email_template_edi_statement', False)
        statement_form = self.env.ref('partner_statement_email.partner_send_statement_wizard', False)

        ctx = dict(
            default_model='res.partner',
            default_res_id=self.id,
            # default_use_template=bool(template),
            # default_template_id=template and template.id or False,
            default_composition_mode='comment',
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'partner.send.statement.wizard',
            'views': [(statement_form.id, 'form')],
            'view_id': statement_form.id,
            'target': 'new',
            'context': ctx,
        }

