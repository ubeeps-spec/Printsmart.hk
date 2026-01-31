from django.db import models
from django.conf import settings

class PageVisit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="使用者")
    path = models.CharField(max_length=255, verbose_name="路徑")
    ip_address = models.GenericIPAddressField(verbose_name="IP 地址")
    user_agent = models.TextField(blank=True, null=True, verbose_name="User Agent")
    referer = models.URLField(blank=True, null=True, verbose_name="來源")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="時間")
    
    # Simple location tracking (Country/City) - could be populated by GeoIP later
    country = models.CharField(max_length=100, blank=True, null=True, verbose_name="國家")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="城市")
    
    # Device info
    device_type = models.CharField(max_length=50, blank=True, null=True, verbose_name="裝置類型") # Mobile, Tablet, Desktop
    browser = models.CharField(max_length=100, blank=True, null=True, verbose_name="瀏覽器")
    os = models.CharField(max_length=100, blank=True, null=True, verbose_name="作業系統")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "訪客紀錄"
        verbose_name_plural = "訪客紀錄"

    def __str__(self):
        return f"{self.path} - {self.timestamp}"


class FileIntegrity(models.Model):
    file_path = models.CharField(max_length=255, unique=True, verbose_name="檔案路徑")
    file_hash = models.CharField(max_length=64, verbose_name="雜湊值") # SHA256
    last_checked = models.DateTimeField(auto_now=True, verbose_name="最後檢查")
    is_modified = models.BooleanField(default=False, verbose_name="是否被修改")

    class Meta:
        verbose_name = "檔案完整性"
        verbose_name_plural = "檔案完整性"

    def __str__(self):
        return self.file_path
