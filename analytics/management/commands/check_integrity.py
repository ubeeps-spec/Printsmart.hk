from django.core.management.base import BaseCommand
from django.conf import settings
from analytics.models import FileIntegrity
from django.core.mail import send_mail
from django.utils import timezone
import hashlib
import os

class Command(BaseCommand):
    help = 'Check integrity of critical files'

    def handle(self, *args, **options):
        # Define critical files/directories
        CRITICAL_FILES = [
            'eshop/settings.py',
            'eshop/urls.py',
            'store/models.py',
            'store/views.py',
            'store/admin.py',
        ]

        changes_detected = []

        for rel_path in CRITICAL_FILES:
            full_path = settings.BASE_DIR / rel_path
            if not full_path.exists():
                self.stdout.write(self.style.WARNING(f'File not found: {rel_path}'))
                continue
                
            with open(full_path, 'rb') as f:
                content = f.read()
                current_hash = hashlib.sha256(content).hexdigest()
            
            integrity_record, created = FileIntegrity.objects.get_or_create(
                file_path=str(rel_path),
                defaults={'file_hash': current_hash}
            )
            
            if not created and integrity_record.file_hash != current_hash:
                changes_detected.append(rel_path)
                integrity_record.file_hash = current_hash
                integrity_record.is_modified = True
                integrity_record.save()
                self.stdout.write(self.style.WARNING(f'Change detected in {rel_path}'))
            else:
                integrity_record.last_checked = timezone.now()
                integrity_record.save()
        
        if changes_detected:
            self.send_alert(changes_detected)
            self.stdout.write(self.style.ERROR('Integrity check failed. Alert sent.'))
        else:
            self.stdout.write(self.style.SUCCESS('Integrity check passed.'))

    def send_alert(self, files):
        subject = 'Security Alert: Critical File Changes Detected'
        message = f"The following files have been modified:\n\n" + "\n".join(files)
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [settings.ADMIN_EMAIL]
        try:
            send_mail(subject, message, from_email, recipient_list, fail_silently=True)
            self.stdout.write(f"Alert sent to {recipient_list}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to send email: {e}"))
