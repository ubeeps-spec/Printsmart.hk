from django.contrib import admin
from django.db.models import Count, Sum, Max, OuterRef, Subquery
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.urls import path
from .models import PageVisit
from store.models import Order
import json
from django.core.serializers.json import DjangoJSONEncoder
# Import the backup admin to ensure it's registered
from . import admin_backup

# @admin.register(PageVisit)
class PageVisitAdmin(admin.ModelAdmin):
    list_display = ('path', 'timestamp', 'ip_address', 'device_type', 'browser', 'country')
    list_filter = ('device_type', 'browser', 'timestamp')
    search_fields = ('path', 'ip_address')
    
    change_list_template = 'admin/analytics_dashboard.html'

    def changelist_view(self, request, extra_context=None):
        from django.utils import timezone
        import datetime
        
        # Date Filter Logic
        period = request.GET.get('period', 'year') # Default to year (Year to date)
        today = timezone.now().date()
        start_date = today.replace(month=1, day=1) # Default start of year
        
        if period == 'today':
            start_date = today
        elif period == 'yesterday':
            start_date = today - datetime.timedelta(days=1)
        elif period == 'week': # Last 7 days
            start_date = today - datetime.timedelta(days=7)
        elif period == 'month': # This month
            start_date = today.replace(day=1)
        elif period == 'last_month':
            last_month_end = today.replace(day=1) - datetime.timedelta(days=1)
            start_date = last_month_end.replace(day=1)
        elif period == 'quarter': # This quarter (simplified)
            month = (today.month - 1) // 3 * 3 + 1
            start_date = today.replace(month=month, day=1)
        elif period == 'year':
            start_date = today.replace(month=1, day=1)
        elif period == 'last_year':
            start_date = today.replace(year=today.year-1, month=1, day=1)
            end_date = today.replace(year=today.year-1, month=12, day=31)
            # Special handling for last year range if needed, but for now let's just filter gte start_date
            # Actually for last_year we want a range.
        
        # Apply filter
        # For simple period implementation, we filter >= start_date.
        # For 'last_year', 'yesterday', 'last_month' we might need an end_date.
        
        date_kwargs = {'timestamp__date__gte': start_date}
        order_kwargs = {'created_at__date__gte': start_date}
        order_item_kwargs = {'order__created_at__date__gte': start_date}

        if period == 'yesterday':
             date_kwargs['timestamp__date__lte'] = start_date
             order_kwargs['created_at__date__lte'] = start_date
             order_item_kwargs['order__created_at__date__lte'] = start_date
        elif period == 'last_month':
             import calendar
             last_month_days = calendar.monthrange(start_date.year, start_date.month)[1]
             end_date = start_date + datetime.timedelta(days=last_month_days-1)
             date_kwargs['timestamp__date__lte'] = end_date
             order_kwargs['created_at__date__lte'] = end_date
             order_item_kwargs['order__created_at__date__lte'] = end_date
        elif period == 'last_year':
             end_date = today.replace(year=today.year-1, month=12, day=31)
             date_kwargs['timestamp__date__lte'] = end_date
             order_kwargs['created_at__date__lte'] = end_date
             order_item_kwargs['order__created_at__date__lte'] = end_date

        # Aggregate daily traffic
        daily_traffic = (
            PageVisit.objects.filter(**date_kwargs)
            .annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        # Total visits for percentage calc
        total_visits_period = PageVisit.objects.filter(**date_kwargs).count() or 1

        # Aggregate browser usage
        browser_usage = (
            PageVisit.objects.filter(**date_kwargs)
            .values('browser')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        browser_usage_list = []
        for b in browser_usage:
            browser_usage_list.append({
                'browser': b['browser'] or 'Unknown',
                'count': b['count'],
                'percent': round((b['count'] / total_visits_period) * 100, 1)
            })
        
        # Aggregate device usage
        device_usage = (
            PageVisit.objects.filter(**date_kwargs)
            .values('device_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        os_usage = (
            PageVisit.objects.filter(**date_kwargs)
            .values('os')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        os_usage_list = []
        for o in os_usage:
            os_usage_list.append({
                'os': o['os'] or 'Unknown',
                'count': o['count'],
                'percent': round((o['count'] / total_visits_period) * 100, 1)
            })

        # Aggregate country usage
        country_usage = (
            PageVisit.objects.filter(**date_kwargs)
            .values('country')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        latest_path_sq = PageVisit.objects.filter(ip_address=OuterRef('ip_address')).order_by('-timestamp').values('path')[:1]
        latest_country_sq = PageVisit.objects.filter(ip_address=OuterRef('ip_address')).order_by('-timestamp').values('country')[:1]
        latest_city_sq = PageVisit.objects.filter(ip_address=OuterRef('ip_address')).order_by('-timestamp').values('city')[:1]
        latest_browser_sq = PageVisit.objects.filter(ip_address=OuterRef('ip_address')).order_by('-timestamp').values('browser')[:1]
        latest_device_sq = PageVisit.objects.filter(ip_address=OuterRef('ip_address')).order_by('-timestamp').values('device_type')[:1]
        most_active_visitors = (
            PageVisit.objects.filter(**date_kwargs)
            .values('ip_address')
            .annotate(
                views=Count('id'),
                last_view=Max('timestamp'),
                latest_page=Subquery(latest_path_sq),
                country=Subquery(latest_country_sq),
                city=Subquery(latest_city_sq),
                browser=Subquery(latest_browser_sq),
                device_type=Subquery(latest_device_sq),
            )
            .order_by('-views')[:20]
        )
        
        # Enrich visitor data with country codes for flags
        most_active_visitors_list = list(most_active_visitors)
        country_map = {
            'Hong Kong': 'hk', 'China': 'cn', 'Taiwan': 'tw', 'United States': 'us', 'USA': 'us',
            'Japan': 'jp', 'United Kingdom': 'gb', 'UK': 'gb', 'Canada': 'ca', 'Australia': 'au',
            'Germany': 'de', 'France': 'fr', 'South Korea': 'kr', 'Singapore': 'sg', 'Malaysia': 'my',
            'Macau': 'mo', 'India': 'in', 'Russia': 'ru', 'Brazil': 'br'
        }
        for v in most_active_visitors_list:
            c_name = v.get('country')
            # Basic mapping, default to empty if not found
            if c_name in country_map:
                v['country_code'] = country_map[c_name]
            else:
                v['country_code'] = ''

        # Prepare data for Chart.js
        chart_labels = [entry['date'].strftime('%Y-%m-%d') for entry in daily_traffic]
        chart_data = [entry['count'] for entry in daily_traffic]
        
        browser_labels = [entry['browser'] for entry in browser_usage]
        browser_data = [entry['count'] for entry in browser_usage]

        device_labels = [entry['device_type'] or 'Unknown' for entry in device_usage]
        device_data = [entry['count'] for entry in device_usage]
        os_labels = [entry['os'] or 'Unknown' for entry in os_usage]
        os_data = [entry['count'] for entry in os_usage]

        country_labels = [entry['country'] or 'Unknown' for entry in country_usage]
        country_data = [entry['count'] for entry in country_usage]
        
        # Sales Analytics
        sales_data = (
            Order.objects.filter(status='paid', **order_kwargs)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(total_sales=Sum('total_amount'))
            .order_by('date')
        )
        sales_labels = [entry['date'].strftime('%Y-%m-%d') for entry in sales_data]
        sales_amounts = [float(entry['total_sales']) for entry in sales_data]
        
        total_sales = Order.objects.filter(status='paid', **order_kwargs).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_orders = Order.objects.filter(**order_kwargs).count()
        
        # Calculate Net Sales (Total - Refunds, simplified here as Total Sales for now)
        net_sales = total_sales 
        
        # Calculate Average Order Value
        avg_order_value = total_sales / total_orders if total_orders > 0 else 0
        
        # Calculate Items Sold
        items_sold = Order.objects.filter(status='paid', **order_kwargs).aggregate(total_items=Sum('items__quantity'))['total_items'] or 0

        # Top Selling Products
        from store.models import OrderItem
        top_products = (
            OrderItem.objects.filter(order__status='paid', **order_item_kwargs)
            .values('product__name')
            .annotate(total_qty=Sum('quantity'), total_sales=Sum('subtotal'))
            .order_by('-total_qty')[:5]
        )
        
        # Top Selling Categories
        top_categories = (
            OrderItem.objects.filter(order__status='paid', **order_item_kwargs)
            .values('product__categories__name')
            .annotate(total_qty=Sum('quantity'), total_sales=Sum('subtotal'))
            .exclude(product__categories__name=None)
            .order_by('-total_qty')[:5]
        )

        extra_context = extra_context or {}
        extra_context['period'] = period
        extra_context['chart_labels'] = json.dumps(chart_labels, cls=DjangoJSONEncoder)
        extra_context['chart_data'] = json.dumps(chart_data, cls=DjangoJSONEncoder)
        extra_context['browser_labels'] = json.dumps(browser_labels, cls=DjangoJSONEncoder)
        extra_context['browser_data'] = json.dumps(browser_data, cls=DjangoJSONEncoder)
        extra_context['browser_usage_list'] = browser_usage_list
        extra_context['device_labels'] = json.dumps(device_labels, cls=DjangoJSONEncoder)
        extra_context['device_data'] = json.dumps(device_data, cls=DjangoJSONEncoder)
        extra_context['os_labels'] = json.dumps(os_labels, cls=DjangoJSONEncoder)
        extra_context['os_data'] = json.dumps(os_data, cls=DjangoJSONEncoder)
        extra_context['os_usage_list'] = os_usage_list
        extra_context['country_labels'] = json.dumps(country_labels, cls=DjangoJSONEncoder)
        extra_context['country_data'] = json.dumps(country_data, cls=DjangoJSONEncoder)
        extra_context['total_visits'] = PageVisit.objects.count()
        # Today Visitors
        extra_context['today_visits'] = PageVisit.objects.filter(timestamp__date=today).count()
        
        extra_context['sales_labels'] = json.dumps(sales_labels, cls=DjangoJSONEncoder)
        extra_context['sales_data'] = json.dumps(sales_amounts, cls=DjangoJSONEncoder)
        extra_context['total_sales'] = total_sales
        extra_context['net_sales'] = net_sales
        extra_context['total_orders'] = total_orders
        extra_context['avg_order_value'] = avg_order_value
        extra_context['items_sold'] = items_sold
        extra_context['top_products'] = top_products
        extra_context['top_categories'] = top_categories
        extra_context['most_active_visitors'] = most_active_visitors_list
        
        return super().changelist_view(request, extra_context=extra_context)

class ShopStatistics(PageVisit):
    class Meta:
        proxy = True
        verbose_name = "網店統計系統"
        verbose_name_plural = "網店統計系統"

@admin.register(ShopStatistics)
class ShopStatisticsAdmin(PageVisitAdmin):
    pass
