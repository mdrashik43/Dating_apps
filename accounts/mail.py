import sys

from django.core.mail.backends.base import BaseEmailBackend


class PlainConsoleEmailBackend(BaseEmailBackend):
    """Development backend: prints emails as plain text so links can be copied
    from the terminal. (Django's console backend prints quoted-printable, which
    mangles long URLs.)"""

    def send_messages(self, email_messages):
        for m in email_messages:
            sys.stdout.write(
                f"\n----- EMAIL -----\nTo: {', '.join(m.to)}\nSubject: {m.subject}\n\n{m.body}\n-----------------\n"
            )
        sys.stdout.flush()
        return len(email_messages)
