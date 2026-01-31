from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html
from django.http import HttpResponse
from django.core.management import call_command
from django.conf import settings
from django.contrib import messages
from .models import Backup
import os
import io

@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ('name', 'backup_type', 'created_at', 'size_formatted', 'action_buttons')
    list_filter = ('backup_type', 'created_at')
    actions = ['delete_selected_backups']
    
    # Disable default add button since we use a custom action
    def has_add_permission(self, request):
        return False

    def size_formatted(self, obj):
        size = obj.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    size_formatted.short_description = "Size"

    def action_buttons(self, obj):
        return format_html(
            '<a class="button" href="download/{}/">Download</a>&nbsp;'
            '<a class="button" href="restore/{}/" onclick="return confirm(\'Are you sure you want to restore this backup? Current data will be overwritten.\')">Restore</a>&nbsp;'
            '<a class="button" style="background-color: #ba2121" href="delete/{}/">Delete</a>',
            obj.pk, obj.pk, obj.pk
        )
    action_buttons.short_description = "Actions"
    action_buttons.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('create/', self.create_backup_view, name='create_backup'),
            path('download/<int:pk>/', self.download_backup_view, name='download_backup'),
            path('restore/<int:pk>/', self.restore_backup_view, name='restore_backup'),
            path('delete/<int:pk>/', self.delete_backup_view, name='delete_backup'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_create_button'] = True
        return super().changelist_view(request, extra_context=extra_context)

    def create_backup_view(self, request):
        backup_type = request.GET.get('type', 'db')
        try:
            if backup_type == 'media':
                # Create Media Backup
                call_command('mediabackup', '--noinput', '--clean')
                target_type = 'media'
            else:
                # Create Database Backup
                call_command('dbbackup', '--noinput', '--clean')
                target_type = 'db'
            
            # Find the latest created backup file
            backup_dir = settings.STORAGES['dbbackup']['OPTIONS']['location']
            files = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, f))]
            
            # Filter files based on expected extension or just take the newest one
            # dbbackup usually creates .psql, .mysql, .sqlite3 etc. or .dump
            # mediabackup usually creates .tar or .tar.gz
            
            if files:
                latest_file = max(files, key=os.path.getctime)
                filename = os.path.basename(latest_file)
                size = os.path.getsize(latest_file)
                
                # Check if this file is already recorded (to avoid duplicates if called quickly)
                if not Backup.objects.filter(name=filename).exists():
                    Backup.objects.create(
                        name=filename,
                        file_path=latest_file,
                        backup_type=target_type,
                        size=size
                    )
                    messages.success(request, f"{target_type.capitalize()} backup created successfully.")
                else:
                     messages.warning(request, "Backup already exists.")
            else:
                messages.error(request, "Backup file not found after creation.")
                
        except Exception as e:
            messages.error(request, f"Error creating backup: {str(e)}")
            
        return redirect('admin:backup_manager_backup_changelist')

    def download_backup_view(self, request, pk):
        backup = Backup.objects.get(pk=pk)
        if os.path.exists(backup.file_path):
            with open(backup.file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type="application/octet-stream")
                response['Content-Disposition'] = 'inline; filename=' + os.path.basename(backup.file_path)
                return response
        messages.error(request, "File not found.")
        return redirect('admin:backup_manager_backup_changelist')

    def restore_backup_view(self, request, pk):
        backup = Backup.objects.get(pk=pk)
        if backup.backup_type == 'db':
            try:
                # Need to implement restore logic carefully
                # call_command('dbrestore', '--noinput', input_filename=backup.name)
                messages.warning(request, "Restore functionality requires careful implementation to avoid data loss. Currently disabled for safety.")
            except Exception as e:
                messages.error(request, f"Error restoring backup: {str(e)}")
        return redirect('admin:backup_manager_backup_changelist')

    def delete_backup_view(self, request, pk):
        backup = Backup.objects.get(pk=pk)
        if os.path.exists(backup.file_path):
            os.remove(backup.file_path)
        backup.delete()
        messages.success(request, "Backup deleted successfully.")
        return redirect('admin:backup_manager_backup_changelist')

    def delete_selected_backups(self, request, queryset):
        for backup in queryset:
            if os.path.exists(backup.file_path):
                os.remove(backup.file_path)
            backup.delete()
        messages.success(request, "Selected backups deleted successfully.")
    delete_selected_backups.short_description = "Delete selected backups"
