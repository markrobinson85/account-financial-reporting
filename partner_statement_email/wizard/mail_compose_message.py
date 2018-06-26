# -*- coding: utf-8 -*-

import base64
import re

from openerp import _, api, fields, models, SUPERUSER_ID
from openerp import tools
from openerp.tools.safe_eval import safe_eval as eval


# main mako-like expression pattern
EXPRESSION_PATTERN = re.compile('(\$\{.+?\})')


def _reopen(self, res_id, model, context=None):
    # save original model in context, because selecting the list of available
    # templates requires a model in context
    context = dict(context or {}, default_model=model)
    return {'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': res_id,
            'res_model': self._name,
            'target': 'new',
            'context': context,
            }


class MailComposer(models.TransientModel):
    """ Generic message composition wizard. You may inherit from this wizard
        at model and view levels to provide specific features.

        The behavior of the wizard depends on the composition_mode field:
        - 'comment': post on a record. The wizard is pre-populated via ``get_record_data``
        - 'mass_mail': wizard in mass mailing mode where the mail details can
            contain template placeholders that will be merged with actual data
            before being sent to each recipient.
    """
    _name = 'mail.compose.message.statement'
    _inherit = 'mail.compose.message'
    _description = 'Email composition wizard'

    @api.model
    def default_get(self, fields):
        """ Handle composition mode. Some details about context keys:
            - comment: default mode, model and ID of a record the user comments
                - default_model or active_model
                - default_res_id or active_id
            - reply: active_id of a message the user replies to
                - default_parent_id or message_id or active_id: ID of the
                    mail.message we reply to
                - message.res_model or default_model
                - message.res_id or default_res_id
            - mass_mail: model and IDs of records the user mass-mails
                - active_ids: record IDs
                - default_model or active_model
        """
        result = super(MailComposer, self).default_get(fields)

        # v6.1 compatibility mode
        result['composition_mode'] = result.get('composition_mode', self._context.get('mail.compose.message.mode', 'comment'))
        result['model'] = result.get('model', self._context.get('active_model'))
        result['res_id'] = result.get('res_id', self._context.get('active_id'))
        result['parent_id'] = result.get('parent_id', self._context.get('message_id'))
        if 'no_auto_thread' not in result and (not result['model'] or not result['model'] in self.pool or not hasattr(self.env[result['model']], 'message_post')):
            result['no_auto_thread'] = True

        # default values according to composition mode - NOTE: reply is deprecated, fall back on comment
        if result['composition_mode'] == 'reply':
            result['composition_mode'] = 'comment'
        vals = {}
        if 'active_domain' in self._context:  # not context.get() because we want to keep global [] domains
            vals['use_active_domain'] = True
            vals['active_domain'] = '%s' % self._context.get('active_domain')
        if result['composition_mode'] == 'comment':
            vals.update(self.get_record_data(result))

        for field in vals:
            if field in fields:
                result[field] = vals[field]

        # TDE HACK: as mailboxes used default_model='res.users' and default_res_id=uid
        # (because of lack of an accessible pid), creating a message on its own
        # profile may crash (res_users does not allow writing on it)
        # Posting on its own profile works (res_users redirect to res_partner)
        # but when creating the mail.message to create the mail.compose.message
        # access rights issues may rise
        # We therefore directly change the model and res_id
        if result['model'] == 'res.users' and result['res_id'] == self._uid:
            result['model'] = 'res.partner'
            result['res_id'] = self.env.user.partner_id.id

        if fields is not None:
            [result.pop(field, None) for field in result.keys() if field not in fields]
        return result

    # @api.model
    # def _get_composition_mode_selection(self):
    #     return [('comment', 'Post on a document'),
    #             ('mass_mail', 'Email Mass Mailing'),
    #             ('mass_post', 'Post on Multiple Documents')]

    # composition_mode = fields.Selection(selection=_get_composition_mode_selection, string='Composition mode', default='comment')
    # partner_ids = fields.Many2many(
    #     'res.partner', 'mail_compose_message_res_partner_rel',
    #     'wizard_id', 'partner_id', 'Additional Contacts')
    # use_active_domain = fields.Boolean('Use active domain')
    # active_domain = fields.Text('Active domain', readonly=True)
    # attachment_ids = fields.Many2many(
    #     'ir.attachment', 'mail_compose_message_ir_attachments_rel',
    #     'wizard_id', 'attachment_id', 'Attachments')
    # is_log = fields.Boolean('Log an Internal Note',
    #                         help='Whether the message is an internal note (comment mode only)')
    # subject = fields.Char(default=False)
    # # mass mode options
    # notify = fields.Boolean('Notify followers', help='Notify followers of the document (mass post only)')
    # template_id = fields.Many2one(
    #     'mail.template', 'Use template', index=True,
    #     domain="[('model', '=', model)]")

    # @api.multi
    # def check_access_rule(self, operation):
    #     """ Access rules of mail.compose.message:
    #         - create: if
    #             - model, no res_id, I create a message in mass mail mode
    #         - then: fall back on mail.message acces rules
    #     """
    #     # Author condition (CREATE (mass_mail))
    #     if operation == 'create' and self._uid != SUPERUSER_ID:
    #         # read mail_compose_message.ids to have their values
    #         message_values = {}
    #         self._cr.execute('SELECT DISTINCT id, model, res_id FROM "%s" WHERE id = ANY (%%s) AND res_id = 0' % self._table, (self.ids,))
    #         for mid, rmod, rid in self._cr.fetchall():
    #             message_values[mid] = {'model': rmod, 'res_id': rid}
    #         # remove from the set to check the ids that mail_compose_message accepts
    #         author_ids = [mid for mid, message in message_values.iteritems()
    #                       if message.get('model') and not message.get('res_id')]
    #         self = self.browse(list(set(self.ids) - set(author_ids)))  # not sure slef = ...
    #
    #     return super(MailComposer, self).check_access_rule(operation)

    @api.multi
    def _notify(self, force_send=False, user_signature=True):
        """ Override specific notify method of mail.message, because we do
            not want that feature in the wizard. """
        return

    @api.model
    def get_record_data(self, values):
        """ Returns a defaults-like dict with initial values for the composition
        wizard when sending an email related a previous email (parent_id) or
        a document (model, res_id). This is based on previously computed default
        values. """
        result, subject = {}, False
        if values.get('parent_id'):
            parent = self.env['mail.message'].browse(values.get('parent_id'))
            result['record_name'] = parent.record_name,
            subject = tools.ustr(parent.subject or parent.record_name or '')
            if not values.get('model'):
                result['model'] = parent.model
            if not values.get('res_id'):
                result['res_id'] = parent.res_id
            partner_ids = values.get('partner_ids', list()) + [(4, id) for id in parent.partner_ids.ids]
            if self._context.get('is_private') and parent.author_id:  # check message is private then add author also in partner list.
                partner_ids += [(4, parent.author_id.id)]
            result['partner_ids'] = partner_ids
        elif values.get('model') and values.get('res_id'):
            doc_name_get = self.env[values.get('model')].browse(values.get('res_id')).name_get()
            result['record_name'] = doc_name_get and doc_name_get[0][1] or ''
            subject = tools.ustr(result['record_name'])

        re_prefix = _('Re:')
        if subject and not (subject.startswith('Re:') or subject.startswith(re_prefix)):
            subject = "%s %s" % (re_prefix, subject)
        result['subject'] = subject

        partner_id = self.env[self._context.get('default_model')].browse(self._context.get('default_res_id'))

        data = {
            'date_end': self._context.get('date_end'),
            # 'statement_type': self._context.get('statement_type'),
            'company_id': partner_id.company_id.id,
            'partner_ids': partner_id.ids,
            # 'partner_to': partner_id.ids + self._context.get('recipient_partner_ids'),
            'show_aging_buckets': self._context.get('show_aging_buckets'),
            'filter_non_due_partners': False,
        }

        pdf = self.env['report'].get_pdf(
                                            partner_id,
                                            self._context.get('statement_type'),
                                            # html=html,
                                            data=data,
                                            # context=self._context
                                        )

        attachment_id = self.env['ir.attachment'].create({
            'name': 'Customer Statement',
            'type': 'binary',
            'datas': base64.encodestring(pdf),
            'datas_fname': 'customer_statement.pdf',
            # 'res_model': 'res.partner',
            # 'res_id': partner_id.id,
            'mimetype': 'application/pdf'
        })

        result['attachment_ids'] = [attachment_id.id]

        # result['partner_ids'] = partner_id.ids + [(4, id) for id in self._context.get('recipient_partner_ids')]
        # result['partner_to'] = partner_id.ids + [(4, id) for id in self._context.get('recipient_partner_ids')]
        #
        # result['partner_ids'] = [(4, id) for id in self._context.get('recipient_partner_ids')]
        # result['partner_to'] = [(4, id) for id in self._context.get('recipient_partner_ids')]

        return result

    @api.multi
    def onchange_template_id(self, template_id, composition_mode, model, res_id):
        """ - mass_mailing: we cannot render, so return the template values
            - normal mode: return rendered values
            /!\ for x2many field, this onchange return command instead of ids
        """
        if template_id and composition_mode == 'mass_mail':
            template = self.env['mail.template'].browse(template_id)
            fields = ['subject', 'body_html', 'email_from', 'reply_to', 'mail_server_id']
            values = dict((field, getattr(template, field)) for field in fields if getattr(template, field))
            if template.attachment_ids:
                values['attachment_ids'] = [att.id for att in template.attachment_ids]
            if template.mail_server_id:
                values['mail_server_id'] = template.mail_server_id.id
            if template.user_signature and 'body_html' in values:
                signature = self.env.user.signature
                values['body_html'] = tools.append_content_to_html(values['body_html'], signature, plaintext=False)
        elif template_id:
            values = self.generate_email_for_composer(template_id, [res_id])[res_id]
            # transform attachments into attachment_ids; not attached to the document because this will
            # be done further in the posting process, allowing to clean database if email not send
            Attachment = self.env['ir.attachment']
            for attach_fname, attach_datas in values.pop('attachments', []):
                data_attach = {
                    'name': attach_fname,
                    'datas': attach_datas,
                    'datas_fname': attach_fname,
                    'res_model': 'mail.compose.message',
                    'res_id': 0,
                    'type': 'binary',  # override default_type from context, possibly meant for another model!
                }
                values.setdefault('attachment_ids', list()).append(Attachment.create(data_attach).id)
        else:
            default_values = self.with_context(default_composition_mode=composition_mode, default_model=model, default_res_id=res_id).default_get(['composition_mode', 'model', 'res_id', 'parent_id', 'partner_ids', 'subject', 'body', 'email_from', 'reply_to', 'attachment_ids', 'mail_server_id'])
            values = dict((key, default_values[key]) for key in ['subject', 'body', 'partner_ids', 'email_from', 'reply_to', 'attachment_ids', 'mail_server_id'] if key in default_values)

        if values.get('body_html'):
            values['body'] = values.pop('body_html')

        # This onchange should return command instead of ids for x2many field.
        # ORM handle the assignation of command list on new onchange (api.v8),
        # this force the complete replacement of x2many field with
        # command and is compatible with onchange api.v7
        values = self._convert_to_write(self._convert_to_cache(values))

        return {'value': values}

    @api.model
    def generate_email_for_composer(self, template_id, res_ids, fields=None):
        """ Call email_template.generate_email(), get fields relevant for
            mail.compose.message, transform email_cc and email_to into partner_ids """
        result = super(MailComposer, self).generate_email_for_composer(template_id, res_ids, fields)

        for res_id in res_ids:
            if result[res_id].get('partner_ids', False):
                result[res_id]['partner_ids'] += self._context.get('recipient_partner_ids')

        return result

