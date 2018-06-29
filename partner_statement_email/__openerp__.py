# -*- coding: utf-8 -*-
# Copyright 2017 Eficent Business and IT Consulting Services S.L.
#   (http://www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Send Partner Statement',
    'version': '9.0.1.0.0',
    'category': 'Accounting & Finance',
    'summary': 'OCA Financial Reports',
    'author': "Eficent, Odoo Community Association (OCA)",
    'website': 'https://github.com/OCA/account-financial-reporting',
    'license': 'AGPL-3',
    'depends': [
        'base', 'customer_outstanding_statement', 'customer_activity_statement',
    ],
    'data': [
        'data/res_partner_statement_mail.xml',
        'data/scheduler_partner_statement.xml',
        'data/scheduler_partner_statement_cron.xml',
        'views/res_partner.xml',
        'wizard/partner_send_statement_wizard.xml',
        'wizard/mail_compose_message_statement.xml',
        'security/ir.model.access.csv',
        'views/scheduler_partner_statement.xml',
    ],
    'installable': True,
    'application': False,
}