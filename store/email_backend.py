from django.core.mail.backends.smtp import EmailBackend
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

class DatabaseEmailBackend(EmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        try:
            from .models import SiteSettings
            config = SiteSettings.objects.first()
            if config and config.smtp_host:
                self.host = config.smtp_host
                self.port = config.smtp_port
                self.username = config.smtp_user
                self.password = config.smtp_password
                self.use_tls = config.smtp_use_tls
                # If you added use_ssl to model, map it here too. 
                # Otherwise default to settings or False.
        except (OperationalError, ProgrammingError):
            # Database might not be ready yet
            pass
    def send_messages(self, email_messages):
        try:
            from .models import SiteSettings
            config = SiteSettings.objects.first()
            if config and config.smtp_from_email:
                for message in email_messages:
                    # If from_email is default, replace it with DB config
                    if not message.from_email or message.from_email == settings.DEFAULT_FROM_EMAIL:
                        message.from_email = config.smtp_from_email
        except Exception:
            pass
            
        return super().send_messages(email_messages)
