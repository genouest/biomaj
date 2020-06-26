from builtins import str
from builtins import object
import smtplib
import email.utils
from biomaj.workflow import Workflow
import logging
import os
import sys
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email import encoders
from jinja2 import Template

if sys.version < '3':
    from email.MIMEText import MIMEText
else:
    from email.mime.text import MIMEText


class Notify(object):
    """
    Send notifications
    """

    @staticmethod
    def notifyBankAction(bank, with_log=True, with_msg=''):
        if not bank.config.get('mail.smtp.host') or bank.session is None:
            logging.info('Notify:none')
            return
        admins = bank.config.get('mail.admin')
        if not admins:
            logging.info('Notify: no mail.admin defined')
            return
        admin_list = admins.split(',')
        logging.info('Notify:' + bank.config.get('mail.admin'))
        mfrom = bank.config.get('mail.from')
        log_file = bank.config.log_file

        msg = MIMEMultipart()

        log_tail = ''
        log_file_size = 0
        if log_file and with_log and os.path.exists(log_file):
            log_file_size = os.path.getsize(log_file)
            max_tail = bank.config.get('mail.body.tail', default=None)
            if max_tail:
                max_tail_length = min(2000000, log_file_size)
                try:
                    max_tail_length = int(max_tail)
                except Exception:
                    logging.exception("invalid mail.body.tail value")
                if max_tail_length > 0:
                    fp = None
                    if sys.version < '3':
                        fp = open(log_file, 'rb')
                    else:
                        fp = open(log_file, 'r')
                    log_tail = fp.read(max_tail_length)
                    fp.close()

        log_attach = bank.config.get('mail.body.attach', default=None)
        if log_attach and with_log and os.path.exists(log_file):
            log_attach_max = 0
            try:
                log_attach_max = int(log_attach)
            except Exception:
                logging.exception("invalid mail.body.attach value")
            if log_attach_max > 0 and log_file_size < log_attach_max:
                logging.debug("attach log file to mail")
                part = None
                with open(log_file, "rb") as attachment:
                    # Add file as application/octet-stream
                    # Email client can usually download this automatically as attachment
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())

                if part:
                    # Encode file in ASCII characters to send by email
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        "attachment; filename=%s" % log_file,
                    )
                    msg.attach(part)

        template_info = {
            'message': with_msg,
            'log_file': log_file,
            'log_tail': log_tail,
            'bank': bank.name,
            'release': str(bank.session.get('release')),
            'status': bank.session.get_status(Workflow.FLOW_OVER),
            'modified': bank.session.get('update') or bank.session.get('remove'),
            'update': bank.session.get('update'),
            'remove': bank.session.get('remove')
        }

        template_file = bank.config.get('mail.template.subject', default=None)
        if template_file and not os.path.exists(template_file):
            logging.error('Template file not found: %s' % template_file)
            template_file = None
        if template_file:
            template = None
            with open(template_file) as file_:
                template = Template(file_.read())
            if template:
                msg['Subject'] = template.render(template_info)
            else:
                logging.error('Failed to render email subject template')
                msg['Subject'] = 'BANK[' + bank.name + '] - STATUS[' + str(bank.session.get_status(Workflow.FLOW_OVER)) + '] - UPDATE[' + str(bank.session.get('update')) + '] - REMOVE[' + str(bank.session.get('remove')) + ']' + ' - RELEASE[' + str(bank.session.get('release')) + ']'
        else:
            msg['Subject'] = 'BANK[' + bank.name + '] - STATUS[' + str(bank.session.get_status(Workflow.FLOW_OVER)) + '] - UPDATE[' + str(bank.session.get('update')) + '] - REMOVE[' + str(bank.session.get('remove')) + ']' + ' - RELEASE[' + str(bank.session.get('release')) + ']'

        template_file = bank.config.get('mail.template.body', None)
        if template_file and not os.path.exists(template_file):
            logging.error('Template file not found: %s' % template_file)
            template_file = None
        if template_file:
            template = None
            with open(template_file) as file_:
                template = Template(file_.read())
            if template:
                msg.attach(MIMEText(template.render(template_info), "plain"))
            else:
                logging.error('Failed to render email subject template')
        else:
            msg.attach(MIMEText(log_tail, "plain"))

        msg['From'] = email.utils.formataddr(('BioMAJ', mfrom))
        logging.info(msg['subject'])
        server = None
        for mto in admin_list:
            msg['To'] = email.utils.formataddr(('Recipient', mto))
            try:
                server = smtplib.SMTP(bank.config.get('mail.smtp.host'), int(bank.config.get('mail.smtp.port', default=25)))
                if bank.config.get('mail.tls') is not None and str(bank.config.get('mail.tls')) == 'true':
                    server.starttls()
                if bank.config.get('mail.user') is not None and str(bank.config.get('mail.user')) != '':
                    server.login(bank.config.get('mail.user'), bank.config.get('mail.password'))
                server.sendmail(mfrom, [mto], msg.as_string())
            except Exception as e:
                logging.exception('Could not send email: ' + str(e))
            finally:
                if server is not None:
                    server.quit()
