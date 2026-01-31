from .models import PageVisit
import re
from django.http import HttpResponseForbidden
import json
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

class WAFMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.sql_injection_patterns = [
            r"union\s+select",
            r"drop\s+table",
            r"delete\s+from",
            r"update\s+.*set",
            r"insert\s+into",
            r"exec\s*\(",
        ]
        self.xss_patterns = [
            r"<script>",
            r"javascript:",
            r"onload\s*=",
            r"onerror\s*=",
        ]
        self.traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
        ]

    def __call__(self, request):
        if self.check_request(request):
            return HttpResponseForbidden("Request blocked by WAF")
        
        response = self.get_response(request)
        return response

    def check_request(self, request):
        # Check GET params
        for value in request.GET.values():
            if self.is_suspicious(value):
                return True
        
        # Check POST params
        for value in request.POST.values():
            if self.is_suspicious(value):
                return True
                
        return False

    def is_suspicious(self, value):
        if not isinstance(value, str):
            return False
        
        value = value.lower()
        for pattern in self.sql_injection_patterns + self.xss_patterns + self.traversal_patterns:
            if re.search(pattern, value):
                return True
        return False


class AnalyticsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Only track GET requests and successful responses
        if request.method == 'GET' and response.status_code == 200:
            # Skip admin and static files
            path = request.path
            if not path.startswith('/admin/') and not path.startswith('/static/') and not path.startswith('/media/'):
                self.record_visit(request)
                
        return response

    def record_visit(self, request):
        ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        referer = request.META.get('HTTP_REFERER', '')
        
        # Basic Device Detection
        ua = user_agent.lower()
        device_type = 'Desktop'
        if 'mobile' in ua or 'iphone' in ua or 'android' in ua and 'mobile' in ua:
            device_type = 'Mobile'
        elif 'ipad' in ua or 'tablet' in ua:
            device_type = 'Tablet'
            
        # Basic Browser Detection
        browser = 'Unknown'
        if 'chrome' in ua and 'safari' in ua:
            browser = 'Chrome'
        elif 'firefox' in ua:
            browser = 'Firefox'
        elif 'safari' in ua and 'chrome' not in ua:
            browser = 'Safari'
        elif 'edg' in ua or 'edge' in ua:
            browser = 'Edge'
        elif 'opera' in ua or 'opr' in ua:
            browser = 'Opera'
        elif 'trident' in ua or 'msie' in ua:
            browser = 'IE'

        # Basic OS Detection
        os_type = 'Unknown'
        if 'windows' in ua:
            os_type = 'Windows'
        elif 'macintosh' in ua or 'mac os' in ua:
            os_type = 'MacOS'
        elif 'linux' in ua and 'android' not in ua:
            os_type = 'Linux'
        elif 'android' in ua:
            os_type = 'Android'
        elif 'ios' in ua or 'iphone' in ua or 'ipad' in ua:
            os_type = 'iOS'
            
        # GeoIP (lightweight, using ipapi.co; safe fallback to Unknown)
        country, city = self.lookup_geo(ip)
        
        PageVisit.objects.create(
            user=request.user if request.user.is_authenticated else None,
            path=request.path,
            ip_address=ip,
            user_agent=user_agent,
            device_type=device_type,
            browser=browser,
            os=os_type,
            country=country,
            referer=referer,
        )

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

# Alias for backward compatibility if needed, though settings should be updated
PageVisitMiddleware = AnalyticsMiddleware

