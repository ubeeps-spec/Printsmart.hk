from django.db import models
import os

class Backup(models.Model):
    BACKUP_TYPES = (
        ('db', 'Database'),
        ('media', 'Media'),
    )

    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=255)
    backup_type = models.CharField(max_length=10, choices=BACKUP_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    size = models.BigIntegerField(help_text="Size in bytes")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def filename(self):
        return os.path.basename(self.file_path)
