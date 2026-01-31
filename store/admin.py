from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from django.contrib.auth.admin import UserAdmin
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV2Checkbox
from .models import Product, ProductImage, Order, OrderItem, SiteSettings, Page, Coupon, OrderNote, Category, Customer, PaymentMethod, SalesDashboard, HeroSlide, UserProfile
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncDate
from django.template.response import TemplateResponse
from django.utils import timezone
import json
from datetime import timedelta
import uuid
from django import forms
from django.forms import CheckboxSelectMultiple
from django.db import models
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ManyToManyWidget
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from openpyxl import Workbook
from django.urls import path
from django.shortcuts import redirect
from django.core.files import File
import zipfile
import tempfile
import os
import re

class RecaptchaAdminLoginForm(AuthenticationForm):
    captcha = ReCaptchaField(widget=ReCaptchaV2Checkbox)

admin.site.login_form = RecaptchaAdminLoginForm

@admin.action(description='複製選取的商品')
def duplicate_product(modeladmin, request, queryset):
    for product in queryset:
        # Capture categories before resetting pk
        categories = list(product.categories.all())
        
        product.pk = None  # Reset primary key to create a new instance
        product.slug = f"{product.slug}-copy" # Update slug to be unique
        product.sku = f"{product.sku}-copy" # Update sku to be unique
        if Product.objects.filter(slug=product.slug).exists():
             import uuid
             product.slug = f"{product.slug}-{uuid.uuid4().hex[:4]}"
        if Product.objects.filter(sku=product.sku).exists():
             import uuid
             product.sku = f"{product.sku}-{uuid.uuid4().hex[:4]}"
             
        product.save()
        
        # Restore categories for the new instance
        product.categories.set(categories)
duplicate_product.short_description = "複製選取的商品"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_active', 'updated_at')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('title', 'image', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    ordering = ('sort_order',)

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('基本設定', {
            'fields': ('site_name', 'logo')
        }),
        ('首頁 Banner 設定', {
            'fields': ('hero_banner', 'hero_title', 'hero_subtitle', 'hero_button_text', 'hero_link')
        }),
        ('聯絡資訊 (Footer)', {
            'fields': ('contact_phone', 'contact_email', 'contact_address', 'footer_about', 'footer_copyright')
        }),
        ('社群媒體', {
            'fields': ('facebook_url', 'instagram_url', 'whatsapp_url')
        }),
        ('外觀設定 (選單與標籤)', {
            'fields': ('top_bar_bg_color', 'navbar_bg_color', 'navbar_text_color', 'navbar_items', 'product_label_bg_color', 'product_label_text_color')
        }),
        ('主選單文字設定', {
            'fields': ('menu_home_text', 'menu_store_text', 'menu_contact_text', 'menu_tutorial_text', 'menu_tutorial_link')
        }),
        ('追蹤代碼', {
            'fields': ('facebook_pixel_id', 'google_analytics_id')
        }),
        ('郵件設定 (SMTP)', {
            'fields': ('smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'smtp_use_tls', 'smtp_from_email'),
            'description': '設定發送系統郵件（如重設密碼）的 SMTP 伺服器資訊。'
        }),
    )

    def has_add_permission(self, request):
        # Disable add button if an instance already exists
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

@admin.action(description='下載匯入範本')
def download_template(modeladmin, request, queryset):
    wb = Workbook()
    ws = wb.active
    ws.title = "Product Template"
    
    # Headers
    headers = ['id', 'name', 'sku', 'price', 'discount_price', 'stock', 'categories', 'description', 'specs', 'image_url', 'image_urls', 'is_active']
    ws.append(headers)
    
    # Sample Row
    ws.append(['', '範例商品', 'SKU-SAMPLE-01', 100, 80, 50, 'HP,Canon', '<p>商品描述...</p>', '<p>規格...</p>', '', 'https://example.com/img1.jpg,https://example.com/img2.jpg', True])
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=product_import_template.xlsx'
    wb.save(response)
    return response

class CleanManyToManyWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            # Handle spaces after commas
            value = ",".join([v.strip() for v in value.split(self.separator) if v.strip()])
        return super().clean(value, row, *args, **kwargs)

class ProductResource(resources.ModelResource):
    categories = fields.Field(
        column_name='categories',
        attribute='categories',
        widget=CleanManyToManyWidget(Category, field='name', separator=',')
    )
    image_urls = fields.Field(column_name='image_urls', attribute='image_urls')

    class Meta:
        model = Product
        fields = ('id', 'name', 'slug', 'sku', 'price', 'discount_price', 'stock', 'categories', 'description', 'specs', 'image_url', 'image_urls', 'is_active')
        import_id_fields = ('id',)
        # We disable skip_unchanged to ensure our custom image processing logic
        # in after_save_instance ALWAYS runs, even if the main fields haven't changed.
        skip_unchanged = False
        report_skipped = True
    
    def dehydrate_image_urls(self, obj):
        urls = []
        if obj.image_url:
            urls.append(obj.image_url)
        for pi in obj.images.all():
            if pi.image_url:
                urls.append(pi.image_url)
            elif pi.image:
                try:
                    urls.append(pi.image.url)
                except Exception:
                    pass
        return ",".join(urls)
    
    def before_import_row(self, row, **kwargs):
        print(f"DEBUG: before_import_row called. keys: {list(row.keys())}", flush=True)
        
        # Support Chinese/Alternate Headers mapping
        # Map common Chinese headers to model fields if the English ones are missing
        header_map = {
            '名稱': 'name', '商品名稱': 'name', '品名': 'name',
            '貨號': 'sku', 'SKU': 'sku',
            '價格': 'price', '售價': 'price',
            '特價': 'discount_price', '優惠價': 'discount_price',
            '庫存': 'stock', '數量': 'stock',
            '分類': 'categories', '類別': 'categories',
            '描述': 'description', '商品描述': 'description',
            '規格': 'specs', '商品規格': 'specs',
            '上架': 'is_active', '是否上架': 'is_active',
        }
        
        for ch_key, en_key in header_map.items():
            if ch_key in row and not row.get(en_key):
                row[en_key] = row[ch_key]

        super().before_import_row(row, **kwargs)
        
        # Ensure non-nullable text fields are empty strings if missing or None
        if row.get('description') is None:
            row['description'] = ''
        if row.get('specs') is None:
            row['specs'] = ''
        if row.get('image_url') is None:
            row['image_url'] = ''
            
        # Handle "No SKU" case by auto-generating one
        # If SKU is missing/empty, generate one from Name or UUID
        sku_val = row.get('sku')
        if not sku_val or str(sku_val).strip() == '':
            import uuid
            # Try to use a sanitized name slug first, else random
            if row.get('name'):
                from django.utils.text import slugify
                base = slugify(str(row.get('name')))[:20].upper()
                if not base: base = "PROD"
                # Add random suffix to ensure uniqueness
                row['sku'] = f"{base}-{uuid.uuid4().hex[:6].upper()}"
            else:
                row['sku'] = f"SKU-{uuid.uuid4().hex[:8].upper()}"

    def before_save_instance(self, instance, row, **kwargs):
        # Check if SKU already exists in another product to prevent IntegrityError crash
        if instance.sku:
            qs = Product.objects.filter(sku=instance.sku)
            if instance.pk:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                # This will be caught by import-export and shown as a row error
                raise Exception(f"錯誤: SKU (貨號) '{instance.sku}' 已存在於另一個商品中，請確保 SKU 唯一。")
        
        super().before_save_instance(instance, row, **kwargs)

    def import_instance(self, instance, row, **kwargs):
        super().import_instance(instance, row, **kwargs)
        
        # Robustly find image URLs from various possible column names
        raw_list = []
        # Check standard fields first
        if row.get('image_urls'):
            raw_list.append(str(row.get('image_urls')))
        
        # Also scan for other likely column names (case-insensitive)
        for key in row.keys():
            k_lower = key.strip().lower()
            # Added Chinese column names support and 'image_urls' (to handle potential trailing spaces in header)
            if k_lower in ['image_urls', 'image_url', 'image url', 'images', 'photo', 'photos', 'pic', 'pics', '圖片', '圖片連結', '照片', '連結']:
                # Avoid adding if it's already caught by the standard 'image_urls' check above
                if key != 'image_urls' and row[key]:
                    raw_list.append(str(row[key]))

        # Join everything found and split by comma to get individual URLs
        full_raw = ",".join(raw_list)
        # Handle full-width comma (common in Chinese input) and other separators
        full_raw = full_raw.replace('，', ',').replace('、', ',')
        
        # Clean URLs: remove whitespace, backticks, and single quotes
        # We also handle non-breaking spaces (\xa0) and ideographic spaces (\u3000) by standard strip()
        all_urls = [u.strip().replace('`', '').replace("'", "") for u in full_raw.split(',') if u and u.strip()]
        
        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for u in all_urls:
            if u not in seen:
                unique_urls.append(u)
                seen.add(u)
        
        instance._import_image_urls = unique_urls
        # Set this attribute so it appears in the import preview
        instance.image_urls = ",".join(unique_urls)
        print(f"DEBUG: Extracted URLs: {unique_urls}")

        # Safety: If obj.image_url (singular) contains commas, it might fail validation.
        # So we clean it up to be just the first URL or empty.
        if instance.image_url and ',' in instance.image_url:
            instance.image_url = instance.image_url.split(',')[0].strip()

        # Double check to ensure fields are not None (in case they were not in row)
        if getattr(instance, 'description', None) is None:
            instance.description = ''
        if getattr(instance, 'specs', None) is None:
            instance.specs = ''
        if getattr(instance, 'image_url', None) is None:
            instance.image_url = ''

    def after_save_instance(self, instance, row, **kwargs):
        super().after_save_instance(instance, row, **kwargs)
        # Note: We do NOT skip dry_run here because we want the preview to show the changes.
        # The transaction rollback mechanism in django-import-export will handle the cleanup.
        
        urls = getattr(instance, '_import_image_urls', [])
        print(f"DEBUG: after_save_instance for {instance.sku}. urls: {urls}")
        
        if urls:
            instance.images.all().delete()
            for idx, u in enumerate(urls):
                ProductImage.objects.create(product=instance, image_url=u, sort_order=idx)
            
            # Repopulate image_urls attribute for the preview display
            instance.image_urls = ",".join(urls)
            
            # Auto-set the main image_url if it's empty but we have imported URLs
            # This ensures the main product has a default image without needing extra queries
            if not instance.image_url and urls:
                print(f"DEBUG: Setting main image_url to {urls[0]}")
                instance.image_url = urls[0]
                instance.save(update_fields=['image_url'])

@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_per_page = 20
    resource_class = ProductResource
    list_display = ('product_thumbnail', 'name', 'sku', 'stock_status', 'price', 'discount_price', 'get_categories', 'is_active', 'updated_at')
    list_filter = ('is_active', 'categories')
    search_fields = ('name', 'sku', 'categories__name')
    prepopulated_fields = {'slug': ('name',)}
    actions = [duplicate_product, download_template]
    list_display_links = ('name', 'product_thumbnail')
    formfield_overrides = {
        models.ManyToManyField: {'widget': CheckboxSelectMultiple},
    }
    
    fieldsets = (
        ('商品資料', {
            'fields': ('name', 'slug', 'sku', 'categories', 'is_active')
        }),
        ('庫存與價格', {
            'fields': ('price', 'discount_price', 'stock')
        }),
        ('詳細描述', {
            'fields': ('description', 'specs')
        }),
        ('圖片', {
            'fields': ('image', 'image_url')
        }),
    )
    
    inlines = []
    
    class ProductImageInline(admin.StackedInline):
        model = ProductImage
        extra = 1
        fields = ('image', 'image_url', 'caption', 'sort_order', 'preview')
        readonly_fields = ('preview',)
        
        def preview(self, obj):
            from django.utils.html import format_html
            if obj.image:
                return format_html('<img src="{}" style="max-height:120px;"/>', obj.image.url)
            elif obj.image_url:
                return format_html('<img src="{}" style="max-height:120px;"/>', obj.image_url)
            return "-"
        preview.short_description = '預覽'
    
    inlines = [ProductImageInline]
    
    def shipping_address_display(self, obj):
        return obj.address
    shipping_address_display.short_description = "運送地址"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('upload-images/', self.admin_site.admin_view(self.upload_images_view), name='store_product_upload_images'),
        ]
        return custom + urls
    
    def upload_images_view(self, request):
        context = {**self.admin_site.each_context(request), 'opts': self.model._meta, 'title': '批次上傳商品圖片 (ZIP)'}
        if request.method == 'POST' and request.FILES.get('zip_file'):
            zf = request.FILES['zip_file']
            tmpdir = tempfile.mkdtemp()
            tmpzip = os.path.join(tmpdir, 'upload.zip')
            with open(tmpzip, 'wb') as f:
                for chunk in zf.chunks():
                    f.write(chunk)
            with zipfile.ZipFile(tmpzip) as z:
                z.extractall(tmpdir)
            created = 0
            updated_products = set()
            for root, _, files in os.walk(tmpdir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        continue
                    full = os.path.join(root, fname)
                    base = os.path.splitext(fname)[0]
                    candidate = re.split(r'[_\-\s]', base)[0]
                    dir_candidate = os.path.basename(root)
                    sku = candidate or dir_candidate
                    try:
                        product = Product.objects.get(sku__iexact=sku)
                    except Product.DoesNotExist:
                        continue
                    sort_order = product.images.count()
                    with open(full, 'rb') as f:
                        django_file = File(f)
                        pi = ProductImage(product=product, sort_order=sort_order)
                        pi.image.save(fname, django_file, save=True)
                        created += 1
                        updated_products.add(product.pk)
                    if not product.image:
                        try:
                            product.image = pi.image
                            product.save()
                        except Exception:
                            pass
            context['result'] = {'created': created, 'updated_products': len(updated_products)}
            from django.contrib import messages
            messages.success(request, f'已建立 {created} 張圖片，更新 {len(updated_products)} 個商品')
            return redirect('admin:store_product_changelist')
        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'admin/store/product/upload_images.html', context)

    def get_categories(self, obj):
        return ", ".join([c.name for c in obj.categories.all()])
    get_categories.short_description = '分類'

    def product_thumbnail(self, obj):
        from django.utils.html import format_html
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />', obj.image.url)
        elif obj.image_url:
             return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />', obj.image_url)
        # Fallback to the first related image if main image is not set
        elif obj.images.exists():
            first_img = obj.images.first()
            if first_img.image_url:
                return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />', first_img.image_url)
            elif first_img.image:
                return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />', first_img.image.url)
        return "-"
    product_thumbnail.short_description = '圖片'

    def stock_status(self, obj):
        from django.utils.html import format_html
        if obj.stock > 0:
            return format_html('<span style="color: green; font-weight: bold;">有庫存 ({})</span>', obj.stock)
        return format_html('<span style="color: red; font-weight: bold;">缺貨</span>')
    stock_status.short_description = '庫存狀態'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('subtotal',)
    verbose_name = "訂單項目"
    verbose_name_plural = "訂單項目"


class OrderNoteInline(admin.StackedInline):
    model = OrderNote
    extra = 1
    verbose_name = "訂單備註"
    verbose_name_plural = "訂單備註"


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_display', 'valid_from', 'valid_to', 'active')
    list_filter = ('active', 'discount_type', 'valid_from', 'valid_to')
    search_fields = ('code', 'description')
    
    fieldsets = (
        (None, {
            'fields': ('code', 'description', 'active')
        }),
        ('折扣設定', {
            'fields': ('discount_type', 'discount')
        }),
        ('有效期', {
            'fields': ('valid_from', 'valid_to')
        }),
    )

    def discount_display(self, obj):
        if obj.discount_type == 'percent':
            return f"{obj.discount}%"
        return f"${obj.discount}"
    discount_display.short_description = "折扣"


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'requires_proof', 'is_active')
    list_filter = ('is_active', 'requires_proof')
    search_fields = ('name', 'code')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'instructions', 'requires_proof', 'is_active')
        }),
    )


class OrderResource(resources.ModelResource):
    items_summary = fields.Field(column_name='購買商品')
    payment_method_display = fields.Field(column_name='付款方式')
    status_display = fields.Field(column_name='訂單狀態')
    created_at_display = fields.Field(column_name='訂單日期')

    class Meta:
        model = Order
        fields = ('order_number', 'created_at_display', 'status_display', 'total_amount', 'customer_name', 'email', 'phone', 'address', 'payment_method_display', 'items_summary')
        export_order = ('order_number', 'created_at_display', 'status_display', 'total_amount', 'items_summary', 'customer_name', 'email', 'phone', 'address', 'payment_method_display')
        import_id_fields = ('order_number',)

    def dehydrate_items_summary(self, order):
        return "; ".join([f"{item.product.name} x{item.quantity}" for item in order.items.all()])

    def dehydrate_payment_method_display(self, order):
        return order.payment_method.name if order.payment_method else ''

    def dehydrate_status_display(self, order):
        return order.get_status_display()

    def dehydrate_created_at_display(self, order):
        return timezone.localtime(order.created_at).strftime('%Y-%m-%d %H:%M')

@admin.register(Order)
class OrderAdmin(ImportExportModelAdmin):
    list_per_page = 20
    resource_class = OrderResource
    change_form_template = 'admin/store/order/change_form.html'
    list_display = ('order_number', 'customer_name', 'status', 'total_amount', 'created_at', 'invoice_link')
    list_filter = ('status', 'payment_method')
    search_fields = ('order_number', 'customer_name', 'email', 'phone')
    inlines = [OrderItemInline]
    readonly_fields = ('order_number', 'invoice_view_link', 'total_amount', 'discount_amount', 'payment_proof_preview', 'ip_address', 'shipping_address_display')

    fieldsets = (
        ('一般', {
            'classes': ('box-general',),
            'fields': ('created_at', 'status', 'user', 'ip_address')
        }),
        ('帳單', {
            'classes': ('box-billing',),
            'fields': ('customer_name', 'address', 'email', 'phone', 'payment_method', 'payment_proof', 'payment_proof_preview')
        }),
        ('運送', {
            'classes': ('box-shipping',),
            'fields': ('shipping_address_display',)
        }),
    )
    
    def shipping_address_display(self, obj):
        return obj.address
    shipping_address_display.short_description = "運送地址"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:order_id>/add-note/', self.admin_site.admin_view(self.add_note_view), name='store_order_add_note'),
            path('<int:note_id>/delete-note/', self.admin_site.admin_view(self.delete_note_view), name='store_order_delete_note'),
            path('get-user-details/<int:user_id>/', self.admin_site.admin_view(self.get_user_details_view), name='store_order_get_user_details'),
            path('get-product-details/<int:product_id>/', self.admin_site.admin_view(self.get_product_details_view), name='store_order_get_product_details'),
        ]
        return custom_urls + urls

    def get_product_details_view(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
            # Ensure Decimals are converted to strings or floats for JSON serialization
            data = {
                'price': str(product.price),
                'discount_price': str(product.discount_price) if product.discount_price else None,
                'effective_price': str(product.effective_price()),
            }
            return JsonResponse(data)
        except Product.DoesNotExist:
             return JsonResponse({'error': 'Product not found'}, status=404)

    def get_user_details_view(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
            data = {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
            # Try to get profile data if exists
            if hasattr(user, 'profile'):
                data['phone'] = user.profile.phone
                data['address'] = user.profile.address
            else:
                 data['phone'] = ''
                 data['address'] = ''
            return JsonResponse(data)
        except User.DoesNotExist:
             return JsonResponse({'error': 'User not found'}, status=404)

    def add_note_view(self, request, order_id):
        if request.method == 'POST':
            order = Order.objects.get(pk=order_id)
            message = request.POST.get('note_content')
            is_customer = request.POST.get('is_customer_note') == 'on'
            if message:
                OrderNote.objects.create(
                    order=order,
                    user=request.user,
                    message=message,
                    is_customer_note=is_customer
                )
                
                if is_customer and order.email:
                    subject = f'訂單備註通知 - {order.order_number}'
                    email_message = f"""
親愛的 {order.customer_name},

您的訂單 {order.order_number} 有新的備註：

{message}

謝謝！
"""
                    try:
                        send_mail(
                            subject,
                            email_message,
                            settings.DEFAULT_FROM_EMAIL,
                            [order.email],
                            fail_silently=True
                        )
                        from django.contrib import messages
                        messages.success(request, '備註已新增並發送郵件給客戶')
                    except Exception as e:
                        from django.contrib import messages
                        messages.warning(request, f'備註已新增，但發送郵件失敗: {e}')
                else:
                    from django.contrib import messages
                    messages.success(request, '備註已新增')
            return redirect('admin:store_order_change', order_id)
        return redirect('admin:store_order_change', order_id)

    def delete_note_view(self, request, note_id):
        note = OrderNote.objects.get(pk=note_id)
        order_id = note.order.id
        note.delete()
        from django.contrib import messages
        messages.success(request, '備註已刪除')
        return redirect('admin:store_order_change', order_id)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            order = Order.objects.get(pk=object_id)
            extra_context['order_notes'] = order.order_notes.all().order_by('-created_at')
            
            # Customer Statistics
            from django.db.models import Sum, Avg
            
            base_qs = None
            if order.user:
                base_qs = Order.objects.filter(user=order.user)
            elif order.email:
                base_qs = Order.objects.filter(email=order.email)
            
            if base_qs is not None:
                # Valid statuses for financial calculations
                valid_statuses = ['paid', 'fulfilling', 'partially_shipped', 'shipped', 'completed']
                
                total_orders = base_qs.count()
                spend_qs = base_qs.filter(status__in=valid_statuses)
                total_spend = spend_qs.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
                aov = spend_qs.aggregate(Avg('total_amount'))['total_amount__avg'] or 0
                
                extra_context['customer_stats'] = {
                    'total_orders': total_orders,
                    'total_spend': total_spend,
                    'aov': aov,
                }
                
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def payment_proof_preview(self, obj):
        from django.utils.html import format_html
        if obj.payment_proof:
             return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 200px; max-width: 300px;" /></a>', obj.payment_proof.url, obj.payment_proof.url)
        return "未上傳"
    payment_proof_preview.short_description = "付款證明預覽"

    def invoice_link(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse
        url = reverse('invoice_view', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank">查看收據</a>', url)
    invoice_link.short_description = '收據'

    def invoice_view_link(self, obj):
        from django.utils.html import format_html
        from django.urls import reverse
        url = reverse('invoice_view', args=[obj.id])
        return format_html('<a href="{}" target="_blank" style="font-size:16px; font-weight:bold;">開啟收據 / 發票</a>', url)
    invoice_view_link.short_description = '列印收據'


class OrderInline(admin.TabularInline):
    model = Order
    fk_name = 'user'
    extra = 0
    readonly_fields = ('order_number', 'created_at', 'status', 'total_amount', 'get_payment_method_name')
    fields = ('order_number', 'created_at', 'status', 'total_amount', 'get_payment_method_name')
    can_delete = False
    show_change_link = True
    ordering = ('-created_at',)
    verbose_name = "訂單記錄"
    verbose_name_plural = "訂單記錄"
    
    def has_add_permission(self, request, obj):
        return False

    def get_payment_method_name(self, obj):
        return obj.payment_method.name if obj.payment_method else "-"
    get_payment_method_name.short_description = '付款方式'

class CustomerChangeForm(UserChangeForm):
    phone = forms.CharField(label='電話', required=False, max_length=30)
    address = forms.CharField(label='地址', required=False, max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            try:
                profile = self.instance.profile
                self.fields['phone'].initial = profile.phone
                self.fields['address'].initial = profile.address
            except UserProfile.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.phone = self.cleaned_data.get('phone', '')
            profile.address = self.cleaned_data.get('address', '')
            profile.save()
        return user

class CustomerResource(resources.ModelResource):
    phone = fields.Field(column_name='Phone')
    address = fields.Field(column_name='Address')
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'date_joined', 'last_login', 'phone', 'address')
        export_order = ('id', 'username', 'email', 'first_name', 'last_name', 'phone', 'address', 'is_active', 'date_joined', 'last_login')
        import_id_fields = ('username',)
        skip_unchanged = True
        report_skipped = False

    def dehydrate_phone(self, user):
        return user.profile.phone if hasattr(user, 'profile') else ''

    def dehydrate_address(self, user):
        return user.profile.address if hasattr(user, 'profile') else ''

    def after_save_instance(self, instance, row, **kwargs):
        if not kwargs.get('dry_run'):
            # Ensure UserProfile exists
            profile, created = UserProfile.objects.get_or_create(user=instance)
            # Update profile fields from row data
            profile.phone = row.get('Phone', '')
            profile.address = row.get('Address', '')
            profile.save()
            
    def before_import_row(self, row, **kwargs):
        # Handle password if needed, or set default
        if 'password' not in row:
             # If no password provided, we might want to set an unusable one or default
             pass

@admin.register(Customer)
class CustomerAdmin(ImportExportModelAdmin, UserAdmin):
    list_per_page = 20
    resource_class = CustomerResource
    form = CustomerChangeForm
    list_display = ('username', 'email', 'order_count', 'total_spend', 'average_order_value', 'last_login', 'date_joined')
    search_fields = ('username', 'email')
    list_filter = ('is_active', 'date_joined')
    inlines = [OrderInline]
    
    fieldsets = (
        ('基本資料', {'fields': ('username', 'password_info', 'last_name', 'first_name', 'email', 'phone', 'address')}),
        ('權限', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('重要日期', {'fields': ('last_login', 'date_joined')}),
    )
    
    readonly_fields = ('password_info',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Only show non-staff users (customers)
        return qs.filter(is_staff=False, is_superuser=False)

    def password_info(self, obj):
        from django.utils.html import format_html
        return format_html(
            '******** <a href="../password/" class="button" style="margin-left: 10px;">重設密碼</a>'
        )
    password_info.short_description = '密碼'

    def order_count(self, obj):
        return Order.objects.filter(user=obj).count()
    order_count.short_description = '訂單數量'

    def total_spend(self, obj):
        from django.db.models import Sum
        # Updated statuses to match Order.STATUS_CHOICES keys
        valid_statuses = ['paid', 'fulfilling', 'partially_shipped', 'shipped', 'completed']
        total = Order.objects.filter(user=obj, status__in=valid_statuses).aggregate(Sum('total_amount'))['total_amount__sum']
        return f"${total:.2f}" if total else "$0.00"
    total_spend.short_description = '消費總額'

    def average_order_value(self, obj):
        from django.db.models import Avg
        valid_statuses = ['paid', 'fulfilling', 'partially_shipped', 'shipped', 'completed']
        avg = Order.objects.filter(user=obj, status__in=valid_statuses).aggregate(Avg('total_amount'))['total_amount__avg']
        return f"${avg:.2f}" if avg else "$0.00"
    average_order_value.short_description = '平均客單價 (AOV)'

@admin.register(SalesDashboard)
class SalesDashboardAdmin(admin.ModelAdmin):
    change_list_template = 'admin/store/salesdashboard/change_list.html'
    
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
        
    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Date Range Filtering
        period = request.GET.get('period', '30days')
        today = timezone.now().date()
        
        if period == 'today':
            start_date = today
            end_date = today
        elif period == '7days':
            start_date = today - timedelta(days=7)
            end_date = today
        elif period == 'this_month':
            start_date = today.replace(day=1)
            end_date = today
        elif period == 'last_month':
            last_month_end = today.replace(day=1) - timedelta(days=1)
            start_date = last_month_end.replace(day=1)
            end_date = last_month_end
        else: # Default 30 days
            start_date = today - timedelta(days=30)
            end_date = today

        # Convert to datetime for filtering
        start_dt = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
        end_dt = timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))
        
        # Base Query: Paid or Completed Orders
        valid_statuses = ['paid', 'fulfilling', 'partially_shipped', 'shipped', 'completed']
        orders = Order.objects.filter(status__in=valid_statuses, created_at__range=(start_dt, end_dt))
        
        # 1. Total Sales
        total_sales = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # 2. Total Orders
        total_orders = orders.count()
        
        # 3. Average Order Value
        avg_order_value = orders.aggregate(Avg('total_amount'))['total_amount__avg'] or 0
        
        # 4. Sales Trend (Daily)
        sales_by_date = orders.annotate(date=TruncDate('created_at'))\
            .values('date')\
            .annotate(daily_sales=Sum('total_amount'), daily_orders=Count('id'))\
            .order_by('date')
            
        # Prepare Chart Data
        chart_labels = []
        chart_data = []
        daily_report = [] # For Table
        
        sales_dict = {item['date']: item for item in sales_by_date}
        
        current_date = start_date
        while current_date <= end_date:
            item = sales_dict.get(current_date, {'daily_sales': 0, 'daily_orders': 0})
            chart_labels.append(current_date.strftime('%Y-%m-%d'))
            chart_data.append(float(item['daily_sales'] or 0))
            
            daily_report.append({
                'date': current_date,
                'sales': item['daily_sales'] or 0,
                'orders': item['daily_orders'] or 0,
                'avg': (item['daily_sales'] or 0) / (item['daily_orders'] or 1) if item['daily_orders'] else 0
            })
            current_date += timedelta(days=1)
            
        # Reverse daily report for table display (newest first)
        daily_report.reverse()
            
        # 5. Top Selling Products
        top_products = OrderItem.objects.filter(order__in=orders)\
            .values('product__name', 'product__sku')\
            .annotate(total_qty=Sum('quantity'), total_revenue=Sum('subtotal'))\
            .order_by('-total_qty')[:10]

        # 6. Payment Method Breakdown
        payment_stats = orders.values('payment_method__name')\
            .annotate(count=Count('id'), total=Sum('total_amount'))\
            .order_by('-total')

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': '銷售報表 Dashboard',
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'total_sales': total_sales,
            'total_orders': total_orders,
            'avg_order_value': avg_order_value,
            'chart_labels': json.dumps(chart_labels),
            'chart_data': json.dumps(chart_data),
            'top_products': top_products,
            'daily_report': daily_report,
            'payment_stats': payment_stats,
        }
        
        return TemplateResponse(request, self.change_list_template, context)

# Unregister default User admin and register custom one to show only staff
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class StaffUserAdmin(UserAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Only show staff users (Backend Users)
        return qs.filter(is_staff=True)
