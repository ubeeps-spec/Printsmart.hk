from django.db import models
from django.utils.text import slugify
from ckeditor.fields import RichTextField
from django.contrib.auth.models import User
import uuid
from django.utils import timezone

class Customer(User):
    class Meta:
        proxy = True
        verbose_name = "客戶"
        verbose_name_plural = "客戶"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="使用者")
    phone = models.CharField(max_length=30, blank=True, verbose_name="電話")
    address = models.CharField(max_length=255, blank=True, verbose_name="地址")
    
    class Meta:
        verbose_name = "使用者資料"
        verbose_name_plural = "使用者資料"

    def __str__(self):
        return f"{self.user.username} 的資料"

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="分類名稱")
    slug = models.SlugField(unique=True, verbose_name="網址代稱")
    
    class Meta:
        verbose_name = "商品分類"
        verbose_name_plural = "商品分類"

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name="商品名稱")
    slug = models.SlugField(max_length=220, unique=True, verbose_name="網址代稱")
    sku = models.CharField(max_length=100, unique=True, verbose_name="貨號")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="價格")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="特價")
    stock = models.PositiveIntegerField(default=0, verbose_name="庫存")
    categories = models.ManyToManyField(Category, blank=True, related_name="products", verbose_name="分類")
    description = RichTextField(blank=True, verbose_name="商品描述")
    specs = RichTextField(blank=True, verbose_name="規格")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="商品圖片")
    image_url = models.URLField(blank=True, verbose_name="圖片連結")
    is_active = models.BooleanField(default=True, verbose_name="上架")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        verbose_name = "商品"
        verbose_name_plural = "商品"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def effective_price(self):
        return self.discount_price if self.discount_price is not None else self.price

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE, verbose_name="商品")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="圖片")
    image_url = models.URLField(blank=True, verbose_name="圖片連結")
    caption = models.CharField(max_length=200, blank=True, verbose_name="說明文字")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    
    class Meta:
        verbose_name = "商品圖片"
        verbose_name_plural = "商品圖片"
        ordering = ['sort_order', 'id']
    
    def __str__(self):
        return f"{self.product.name} 圖片 #{self.id}"

class Page(models.Model):
    title = models.CharField(max_length=200, verbose_name="標題")
    slug = models.SlugField(unique=True, verbose_name="網址代稱")
    content = RichTextField(verbose_name="內容")
    is_active = models.BooleanField(default=True, verbose_name="啟用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        verbose_name = "頁面"
        verbose_name_plural = "頁面"

    def __str__(self):
        return self.title

class PaymentMethod(models.Model):
    name = models.CharField(max_length=100, verbose_name="名稱")
    code = models.CharField(max_length=50, unique=True, verbose_name="代碼")
    description = models.TextField(blank=True, verbose_name="描述")
    instructions = RichTextField(blank=True, verbose_name="付款指示 (顯示於結帳頁)")
    requires_proof = models.BooleanField(default=False, verbose_name="需要上傳證明")
    is_active = models.BooleanField(default=True, verbose_name="啟用")
    
    class Meta:
        verbose_name = "付款方式"
        verbose_name_plural = "付款方式"

    def __str__(self):
        return self.name

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="優惠碼")
    description = models.TextField(blank=True, verbose_name="描述")
    discount_type = models.CharField(max_length=20, choices=[('percent', '百分比'), ('fixed', '固定金額')], default='percent', verbose_name="折扣類型")
    discount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="折扣數值")
    valid_from = models.DateTimeField(verbose_name="生效時間")
    valid_to = models.DateTimeField(verbose_name="過期時間")
    active = models.BooleanField(default=True, verbose_name="啟用")

    class Meta:
        verbose_name = "優惠券"
        verbose_name_plural = "優惠券"

    def __str__(self):
        return self.code

    def calculate_discount(self, total):
        if self.discount_type == 'percent':
             return total * (self.discount / 100)
        return self.discount

class Order(models.Model):
    STATUS_CHOICES = [
        ('created', '已建立'),
        ('paid', '已付款'),
        ('fulfilling', '備貨中'),
        ('partially_shipped', '部份交付'),
        ('shipped', '已出貨'),
        ('completed', '已完成'),
        ('canceled', '已取消'),
        ('returned', '退貨'),
        ('refunded', '已退費'),
    ]

    order_number = models.CharField(max_length=50, unique=True, editable=False, verbose_name="訂單編號", null=True)
    user = models.ForeignKey(User, related_name='orders', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="會員帳號")
    customer_name = models.CharField(max_length=100, verbose_name="客戶名稱")
    email = models.EmailField(verbose_name="電子郵件")
    phone = models.CharField(max_length=30, blank=True, verbose_name="電話")
    address = models.CharField(max_length=255, verbose_name="地址")
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="IP 地址")
    notes = models.TextField(blank=True, verbose_name="備註")
    coupon = models.ForeignKey(Coupon, related_name='orders', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="優惠券")
    payment_method = models.ForeignKey(PaymentMethod, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="付款方式")
    payment_proof = models.ImageField(upload_to='payment_proofs/', blank=True, null=True, verbose_name="付款證明 (入數紙)")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="折扣金額")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', verbose_name="狀態")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="總金額")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="訂單時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        verbose_name = "訂單"
        verbose_name_plural = "訂單"

    def __str__(self):
        return f'{self.order_number} - {self.customer_name}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            now = timezone.now()
            self.order_number = f"ORD-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE, verbose_name="訂單")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="商品")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="單價")
    quantity = models.PositiveIntegerField(default=1, verbose_name="數量")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="小計")

    class Meta:
        verbose_name = "訂單項目"
        verbose_name_plural = "訂單項目"

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.product.discount_price if self.product.discount_price else self.product.price
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

class OrderNote(models.Model):
    order = models.ForeignKey(Order, related_name='order_notes', on_delete=models.CASCADE, verbose_name="訂單")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="使用者")
    message = models.TextField(verbose_name="內容")
    is_customer_note = models.BooleanField(default=False, verbose_name="發送給客戶")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="時間")

    class Meta:
        verbose_name = "訂單備註"
        verbose_name_plural = "訂單備註"
    
    def __str__(self):
        return f"Note for {self.order}"

class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default="My E-Shop", verbose_name="網站名稱")
    logo = models.ImageField(upload_to='site/', blank=True, null=True, verbose_name="Logo")
    hero_banner = models.ImageField(upload_to='site/', blank=True, null=True, verbose_name="首頁 Banner")
    hero_title = models.CharField(max_length=200, blank=True, verbose_name="Banner 標題")
    hero_subtitle = models.CharField(max_length=200, blank=True, verbose_name="Banner 副標題")
    hero_button_text = models.CharField(max_length=50, blank=True, verbose_name="按鈕文字")
    hero_link = models.URLField(blank=True, verbose_name="Banner 連結")
    
    contact_phone = models.CharField(max_length=50, blank=True, verbose_name="聯絡電話")
    contact_email = models.EmailField(blank=True, verbose_name="聯絡 Email")
    contact_address = models.CharField(max_length=255, blank=True, verbose_name="聯絡地址")
    
    footer_about = models.TextField(blank=True, verbose_name="Footer 關於我們")
    footer_copyright = models.CharField(max_length=200, blank=True, default="Copyright © 2026 PrintSmart.hk", verbose_name="Footer 版權宣告")
    
    facebook_url = models.URLField(blank=True, verbose_name="Facebook 連結")
    instagram_url = models.URLField(blank=True, verbose_name="Instagram 連結")
    whatsapp_url = models.URLField(blank=True, verbose_name="WhatsApp 連結")
    
    # Tracking Pixels
    facebook_pixel_id = models.CharField(max_length=50, blank=True, help_text="Example: 123456789", verbose_name="Facebook Pixel ID")
    google_analytics_id = models.CharField(max_length=50, blank=True, help_text="Example: G-XXXXXXXXXX", verbose_name="Google Analytics ID")
    
    # SMTP Email Settings
    smtp_host = models.CharField(max_length=200, blank=True, verbose_name="SMTP 主機 (Host)")
    smtp_port = models.IntegerField(default=587, verbose_name="SMTP 端口 (Port)")
    smtp_user = models.CharField(max_length=200, blank=True, verbose_name="SMTP 帳號 (User)")
    smtp_password = models.CharField(max_length=200, blank=True, verbose_name="SMTP 密碼 (Password)")
    smtp_use_tls = models.BooleanField(default=True, verbose_name="使用 TLS")
    smtp_from_email = models.EmailField(blank=True, verbose_name="寄件者 Email")

    # Main Menu Text Customization
    menu_home_text = models.CharField(max_length=50, default="主頁", verbose_name="主選單-主頁文字")
    menu_store_text = models.CharField(max_length=50, default="商店", verbose_name="主選單-商店文字")
    menu_contact_text = models.CharField(max_length=50, default="聯絡我們", verbose_name="主選單-聯絡我們文字")
    menu_tutorial_text = models.CharField(max_length=50, default="購物流程教學", verbose_name="主選單-教學文字")
    menu_tutorial_link = models.CharField(max_length=200, default="#", verbose_name="主選單-教學連結")

    # Colors
    top_bar_bg_color = models.CharField(max_length=20, default="#F50057", verbose_name="頂部通知列背景顏色", help_text="Hex color code (e.g. #F50057)")
    navbar_bg_color = models.CharField(max_length=20, default="#D32F2F", verbose_name="導航列背景顏色", help_text="Hex color code (e.g. #D32F2F)")
    navbar_text_color = models.CharField(max_length=20, default="#ffffff", verbose_name="導航列文字顏色", help_text="Hex color code (e.g. #ffffff)")
    navbar_items = models.TextField(default="HP, CANON, BROTHER, EPSON, SAMSUNG, XEROX, PANTUM, LEXMARK, KODAK, 其他商品", verbose_name="導航列項目", help_text="Comma separated list")
    product_label_bg_color = models.CharField(max_length=20, default="#D32F2F", verbose_name="商品標籤背景顏色")
    product_label_text_color = models.CharField(max_length=20, default="#ffffff", verbose_name="商品標籤文字顏色")

    class Meta:
        verbose_name = "網站設定"
        verbose_name_plural = "網站設定"

    def __str__(self):
        return self.site_name
        
    def get_navbar_items_list(self):
        if self.navbar_items:
            return [item.strip() for item in self.navbar_items.split(',')]
        return []

class HeroSlide(models.Model):
    image = models.ImageField(upload_to='hero_slides/', verbose_name="圖片", help_text="建議尺寸: 1920x450 像素 (寬x高)")
    title = models.CharField(max_length=200, blank=True, verbose_name="標題")
    subtitle = models.CharField(max_length=200, blank=True, verbose_name="副標題")
    button_text = models.CharField(max_length=50, blank=True, verbose_name="按鈕文字")
    link = models.URLField(blank=True, verbose_name="連結")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序")
    is_active = models.BooleanField(default=True, verbose_name="啟用")

    class Meta:
        verbose_name = "首頁輪播圖"
        verbose_name_plural = "首頁輪播圖"
        ordering = ['sort_order']

    def __str__(self):
        return self.title or f"Slide #{self.id}"

class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist', verbose_name="會員")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by', verbose_name="商品")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="加入時間")

    class Meta:
        verbose_name = "我的最愛"
        verbose_name_plural = "我的最愛"
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

class SalesDashboard(models.Model):
    class Meta:
        managed = False
        verbose_name = '銷售報表 Dashboard'
        verbose_name_plural = '銷售報表 Dashboard'
