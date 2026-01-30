from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.core.management import call_command
from django.contrib import messages
from django.conf import settings
import os
import datetime

# This is a proxy model just to register in admin
from .models import PageVisit

class BackupManager(PageVisit):
    class Meta:
        proxy = True
        verbose_name = "Backup Manager"
        verbose_name_plural = "Backup Manager"

@admin.register(BackupManager)
class BackupManagerAdmin(admin.ModelAdmin):
    change_list_template = 'admin/backup_manager.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('create_backup/', self.admin_site.admin_view(self.create_backup), name='create_backup'),
            path('restore_backup/<str:filename>/', self.admin_site.admin_view(self.restore_backup), name='restore_backup'),
            path('delete_backup/<str:filename>/', self.admin_site.admin_view(self.delete_backup), name='delete_backup'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        backup_dir = settings.BASE_DIR / 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        backups = []
        if os.path.exists(backup_dir):
            for f in os.listdir(backup_dir):
                if f.endswith('.dump') or f.endswith('.psql') or f.endswith('.sqlite3') or f.endswith('.json') or f.endswith('.tar') or f.endswith('.tar.gz'):
                    path = os.path.join(backup_dir, f)
                    stat = os.stat(path)
                    backups.append({
                        'name': f,
                        'size': f"{stat.st_size / (1024*1024):.2f} MB",
                        'date': datetime.datetime.fromtimestamp(stat.st_mtime),
                        'type': 'Media' if 'media' in f or f.endswith('.tar') else 'Database'
                    })
        
        # Sort by date desc
        backups.sort(key=lambda x: x['date'], reverse=True)
        
        extra_context = extra_context or {}
        extra_context['backups'] = backups
        return super().changelist_view(request, extra_context=extra_context)

    def create_backup(self, request):
        try:
            call_command('dbbackup', '--noinput')
            call_command('mediabackup', '--noinput')
            messages.success(request, 'System backup (Database + Media) created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating backup: {str(e)}')
        
        return redirect('admin:analytics_backupmanager_changelist')

    def restore_backup(self, request, filename):
        try:
            if 'media' in filename or filename.endswith('.tar') or filename.endswith('.tar.gz'):
                call_command('mediarestore', '--noinput', input_filename=filename)
                messages.success(request, f'Media restored from {filename}!')
            else:
                call_command('dbrestore', '--noinput', input_filename=filename)
                messages.success(request, f'Database restored from {filename}!')
        except Exception as e:
            messages.error(request, f'Error restoring backup: {str(e)}')
        
        return redirect('admin:analytics_backupmanager_changelist')

    def delete_backup(self, request, filename):
        try:
            backup_dir = settings.BASE_DIR / 'backups'
            file_path = os.path.join(backup_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                messages.success(request, f'Backup {filename} deleted successfully!')
            else:
                messages.error(request, 'File not found.')
        except Exception as e:
            messages.error(request, f'Error deleting backup: {str(e)}')
        
        return redirect('admin:analytics_backupmanager_changelist')
