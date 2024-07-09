###############################################################################
# email_report.py
#
# This module provides the Email class.
#
# - set up communication with SMTP server
# - set up mail header
# - send mail
#
# created: 01/2021 updated: 05/2021
#
# This program is Copyright (C) 01/2021 Matthias Prinke
# <m.prinke@arcor.de> and covered by GNU's GPL.
# In particular, this program is free software and comes WITHOUT
# ANY WARRANTY.
#
# History:
#
# 20210117 Extracted from flora.py
# 20210203 Added support for MicroPython by using uMail
#          Using micropython-lib/email.massage would not work due to a bug
#          in datetime.py 
#          (see https://github.com/micropython/micropython/pull/3391)
#          Thus, the mail header is created manually. 
# 20210207 Changed to allow sending email in smaller chunks
#          due to ESP memory constraints
# 20210208 Replaced config by settings
# 20210508 Added exception handling for SMTP constructor call
#
# ToDo:
#
# - 
#
###############################################################################

import sys
import ssl

if sys.implementation.name == "micropython":
    import umail
    import uerrno
else:
    from unidecode import unidecode
    import smtplib
    from email.message import EmailMessage

from garbage_collect import gcollect, meminfo
from config import settings, DEBUG, VERBOSITY, MEMINFO
from print_line import print_line


###############################################################################
# Email class - Setup email object from settings and send message 
###############################################################################
class Email:
    """
    Handle e-Mails
    
    Attributes:
        settings (Settings):   instance of Settings class
        content  (string):     content buffer (used with smtplib only)
        smtp     (SMTP):       instance of SMTP class (from uMail or smtplib, respectively)
        
    """
    def __init__(self, settings):
        """
        The constructor for Email class.

        Parameters:
            settings (Settings): Settings object instance
        """
        self.settings = settings
        self.content = ""
        self.smtp = 0
        
        if MEMINFO:
            meminfo('Email: init')

        if (VERBOSITY > 1):
            print_line('E-Mail settings: {:s}, {:d}, {:s}, {:s}'\
                       .format(self.settings.smtp_server, 
                               self.settings.smtp_port, 
                               self.settings.smtp_email, 
                               self.settings.smtp_receiver))
        gcollect()
        
    def smtp_begin(self):
        if sys.implementation.name == "micropython":
            return self._umail_begin()
        else:
            return self._smtplib_begin()

    def _umail_begin(self):
        """
        Send report as mail.
        
        Uses uMail (which relies on ssl internally) 
        The mail header is created manually.
            
        Returns:
            bool: success
        """
        if (VERBOSITY > 0):
            print_line('uMail: trying to send message...', console=True, sd_notify=True)
        
        if MEMINFO:
            meminfo('Email: _umail_begin - start')
        
        try:
            # n.b.: ssl=False enforces STARTTLS
            self.smtp = umail.SMTP(self.settings.smtp_server, self.settings.smtp_port, ssl=False)
        except OSError as exc:
            if (len(exc.args) > 1):
                print_line('uMail: ...failed ({})!'.format(exc.args[1]), error=True, console=True, sd_notify=True)
            else:
                print_line('uMail: ...failed!', error=True, console=True, sd_notify=True)
            return False
        
        if MEMINFO:
            meminfo('Email: _umail_begin - smtp object created')

        if (VERBOSITY > 1):
            print_line('uMail:     init():  {}'.format(self.smtp), console=True, sd_notify=True)
        
        rc = self.smtp.login(self.settings.smtp_login, self.settings.smtp_passwd)
        if (VERBOSITY > 1):
            print_line('uMail:     login(): {}'.format(rc), console=True, sd_notify=True)
        
        rc = self.smtp.to(self.settings.smtp_receiver, self.settings.smtp_email)
        if (VERBOSITY > 1):
            print_line('uMail:     to():    {}'.format(rc), console=True, sd_notify=True)
        
        # create mail header, empty line with \r\n indicates end-of-header
        self.smtp.write("From: <" + self.settings.smtp_email + ">\r\n")
        self.smtp.write("To: <" + self.settings.smtp_receiver + ">\r\n")
        self.smtp.write("MIME-Version: 1.0\r\n")
        self.smtp.write("Content-type: text/html; charset=utf-8\r\n")
        self.smtp.write("Subject: Flora Status\r\n\r\n")
        
        return True
    
    def _smtplib_begin(self):
        """
        Send report as mail.
        
        Uses smtplib, email.message and ssl 

        Parameters:
            content (string): mail content
            
        Returns:
            bool: success
        """
        context = ssl.create_default_context()
        success = True

        try:
            self.smtp = smtplib.SMTP(self.settings.smtp_server, self.settings.smtp_port)
            if (DEBUG):
                self.smtp.set_debuglevel(1)
            self.smtp.ehlo()  # Can be omitted
            self.smtp.starttls(context = context)
            self.smtp.ehlo()  # Can be omitted
            self.smtp.login(self.settings.smtp_login, self.settings.smtp_passwd)

        except:
            success = False

        return success

        
    def smtp_write(self, content):
        if sys.implementation.name != "micropython":
            self.content += unidecode(content)
        else:
            self.smtp.write(content)

    def smtp_finish(self):
        if sys.implementation.name != "micropython":
            success = True
            msg = EmailMessage()
            msg['Subject'] = "Flora Status"
            msg['From'] = self.settings.smtp_email
            msg['To'] = self.settings.smtp_receiver
            msg.set_content(self.content, subtype='html')

            try:
                self.smtp.send_message(msg)

            except:
                success = False

            finally:
                if self.smtp:
                    self.smtp.quit()

            return success

        else:
            rc = self.smtp.send()
            if (VERBOSITY > 1):        
                print_line('uMail:     send():  {}'.format(rc), console=True, sd_notify=True)
            
            if (VERBOSITY > 0):
                print_line('uMail: ...success!', console=True, sd_notify=True)
            
            if self.smtp:
                self.smtp.quit()
                return True
