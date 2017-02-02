from builtins import str
from builtins import object
import smtplib
import email.utils
from biomaj.workflow import Workflow
import logging
import sys
if sys.version < '3':
    from email.MIMEText import MIMEText
else:
    from email.mime.text import MIMEText


class Notify(object):
    """
    Send notifications
    """

    @staticmethod
    def notifyBankAction(bank):
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
        msg = MIMEText('')
        if log_file:
            fp = None
            if sys.version < '3':
                fp = open(log_file, 'rb')
            else:
                fp = open(log_file, 'r')
            msg = MIMEText(fp.read(2000000))
            fp.close()

        msg['From'] = email.utils.formataddr(('Author', mfrom))
        msg['Subject'] = 'BANK[' + bank.name + '] - STATUS[' + str(bank.session.get_status(Workflow.FLOW_OVER)) + '] - UPDATE[' + str(bank.session.get('update')) + '] - REMOVE[' + str(bank.session.get('remove')) + ']' + ' - RELEASE[' + str(bank.session.get('release')) + ']'

        logging.info(msg['subject'])
        server = None
        for mto in admin_list:
            msg['To'] = email.utils.formataddr(('Recipient', mto))
            try:
                server = smtplib.SMTP(bank.config.get('mail.smtp.host'))
                if bank.config.get('mail.tls') is not None and str(bank.config.get('mail.tls')) == 'true':
                    server.starttls()
                if bank.config.get('mail.user') is not None and str(bank.config.get('mail.user')) != '':
                    server.login(bank.config.get('mail.user'), bank.config.get('mail.password'))
                server.sendmail(mfrom, [mto], msg.as_string())
            except Exception as e:
                logging.error('Could not send email: ' + str(e))
            finally:
                if server is not None:
                    server.quit()
