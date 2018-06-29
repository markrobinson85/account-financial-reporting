# -*- coding: utf-8 -*-

import json
from lxml import etree
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from openerp import api, fields, models, _
from openerp.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.misc import formatLang

from openerp.exceptions import UserError, RedirectWarning, ValidationError

import openerp.addons.decimal_precision as dp
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.multi
    def action_partner_statement_send(self):
        """ Open a window to compose an email
        """
        self.ensure_one()
        statement_form = self.env.ref('partner_statement_email.partner_send_statement_wizard', False)

        ctx = dict(
            default_model='res.partner',
            default_res_id=self.id,
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

    @api.one
    def statement_quick_send(self, context=False):
        message_id = self.env['mail.compose.message.statement'].create({
            'template_id': self._context.get('default_template_id')
        })

        values = message_id.onchange_template_id(
                                        template_id=self._context.get('default_template_id'),
                                        composition_mode=self._context.get('default_composition_mode'),
                                        model=self._context.get('default_model'),
                                        res_id=self._context.get('default_res_id'))

        message_id.write(values['value'])
        message_id.send_mail_action()

        return message_id


class SchedulerCustomerStatement(models.Model):
    _name = "scheduler.partner.statement"
    _inherit = ['mail.thread']
    _description = 'Partner Statement Subscription'

    name = fields.Char('Number',
                       readonly=True,
                       default=lambda self: self.env['ir.sequence'].next_by_code(
                           'scheduler.partner.statement'))

    partner_id = fields.Many2one('res.partner', 'Partner Account', track_visibility='onchange',)

    recipient_ids = fields.Many2many(
        'res.partner', 'scheduler_partner_statement_res_partner_rel',
        'scheduler_id', 'partner_id', 'Recipients')

    user_id = fields.Many2one('res.users', string='User', required=True, track_visibility='onchange',)

    active = fields.Boolean('Active', track_visibility='onchange',)

    statement_type = fields.Selection([('customer_outstanding_statement.statement', 'Oustanding Statement'),
                                       ('customer_activity_statement.statement', 'Activity Statement')],
                                      'Statement Type',
                                      track_visibility='onchange',
                                      default='customer_outstanding_statement.statement')

    show_aging_buckets = fields.Boolean(string='Include Aging Buckets',
                                        track_visibility='onchange',
                                        default=False)

    date_last_sent = fields.Date('Last Sent',
                                 # track_visibility='onchange',
                                 readonly=True)

    date_next_send = fields.Date('Scheduled Send Date',
                                 track_visibility='onchange',
                                 help='Odoo will automatically send the '
                                      'customer the statement on this date.')

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company'
    )

    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)

    dont_send_when_zero = fields.Boolean("Don't send zero balance statements", default=True, track_visibility='onchange',)

    credit = fields.Monetary(string='Total Receivable', help="Total amount this customer owes you.",
                             currency_field='company_currency_id',
                             related='partner_id.credit')

    @api.multi
    def set_thirty_days_later(self):
        for schedule_id in self:
            thirty_days_later = date.today() + relativedelta(months=+1)
            if thirty_days_later.weekday() in [5, 6]:
                schedule_id.date_next_send = fields.Date.to_string(thirty_days_later + relativedelta(weekday=0))
            else:
                schedule_id.date_next_send = fields.Date.to_string(thirty_days_later)

    @api.model
    def process_scheduler_queue(self):
        # Find schedulers that were last executed more than 30 days earlier.
        schedulers = self.search(['|', ('date_next_send', '<=', datetime.strftime(fields.datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)), ('date_next_send', '=', False)])
        today = date.today()
        for schedule_id in schedulers:
            if schedule_id.date_next_send is not False and fields.Date.from_string(schedule_id.date_next_send) > today:
                continue
            if schedule_id.dont_send_when_zero and schedule_id.partner_id.credit == 0:
                schedule_id.set_thirty_days_later()
                continue

            if schedule_id.statement_type == 'customer_outstanding_statement.statement':
                template = self.env.ref('partner_statement_email.email_template_outstanding_statement', False)
            else:
                template = self.env.ref('partner_statement_email.email_template_activity_statement', False)

            date_start = fields.Date.to_string(date.today() - timedelta(days=120))
            date_end = fields.Date.to_string(date.today())

            context = dict(
                default_model='scheduler.partner.statement',
                default_res_id=schedule_id.id, #.partner_id.commercial_partner_id.id,
                default_use_template=bool(template),
                default_template_id=template and template.id or False,
                default_composition_mode='comment',
                default_statement_type=schedule_id.statement_type,
                date_start=date_start,
                date_end=date_end,
                default_partner_to=schedule_id.partner_id.commercial_partner_id.id,
                recipient_partner_ids=schedule_id.recipient_ids.ids,
                show_aging_buckets=schedule_id.show_aging_buckets,
                statement_type=schedule_id.statement_type,
                uid=schedule_id.user_id.id,
                schedule_id=schedule_id.id
            )

            schedule_id.partner_id.sudo(schedule_id.user_id.id).with_context(context).statement_quick_send()

