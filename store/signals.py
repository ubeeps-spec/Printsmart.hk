from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
import datetime

@receiver(user_logged_in)
def notify_admin_login(sender, user, request, **kwargs):
    if user.is_superuser:
        # Get IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        subject = f'Security Alert: Admin Login Detected - {user.username}'
        message = f"""
        Alert: An administrator account has logged into the system.
        
        User: {user.username}
        Time: {datetime.datetime.now()}
        IP Address: {ip}
        User Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}
        
        If this was not you, please immediately lock your account and contact support.
        """
        
        # Use configured admin email or fallback to user's email
        admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@example.com')
        recipient_list = [admin_email]
        if user.email and user.email != admin_email:
            recipient_list.append(user.email)
            
        try:
            print(f"Sending login notification to {recipient_list}")
            send_mail(
                subject, 
                message, 
                settings.DEFAULT_FROM_EMAIL, 
                recipient_list, 
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send login notification: {e}")

from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum
from .models import Order, OrderItem, UserProfile

@receiver(pre_save, sender=Order)
def restore_stock_on_cancel(sender, instance, **kwargs):
    if not instance.pk:
        return
        
    try:
        old_order = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return
        
    # If changing TO canceled/refunded/returned FROM valid status
    if instance.status in ['canceled', 'refunded', 'returned'] and old_order.status not in ['canceled', 'refunded', 'returned']:
        for item in instance.items.all():
            product = item.product
            product.stock += item.quantity
            product.save()
            
    # If changing FROM canceled/refunded/returned TO valid status (re-opening order)
    elif old_order.status in ['canceled', 'refunded', 'returned'] and instance.status not in ['canceled', 'refunded', 'returned']:
        for item in instance.items.all():
            product = item.product
            # Allow stock to go negative if manually re-opened by admin
            product.stock -= item.quantity
            product.save()

@receiver(pre_save, sender=Order)
def log_status_change(sender, instance, **kwargs):
    from .models import OrderNote
    
    if not instance.pk:
        return
        
    try:
        old_order = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return
        
    if instance.status != old_order.status:
        message = f"Order status changed from '{old_order.get_status_display()}' to '{instance.get_status_display()}'."
        OrderNote.objects.create(
            order=instance,
            message=message
        )

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

@receiver([post_save, post_delete], sender=OrderItem)
def update_order_total(sender, instance, **kwargs):
    """
    Automatically recalculate Order total_amount when OrderItems are saved or deleted.
    """
    order = instance.order
    # Calculate sum of subtotals
    items_total = order.items.aggregate(total=Sum('subtotal'))['total'] or 0
    
    # Subtract discount if applicable
    final_total = items_total - (order.discount_amount or 0)
    
    # Ensure non-negative
    if final_total < 0:
        final_total = 0
        
    # Only update if changed to avoid unnecessary DB writes
    if order.total_amount != final_total:
        order.total_amount = final_total
        # Use update_fields to minimize side effects, but we must ensure updated_at is handled if needed.
        # However, save(update_fields=...) doesn't update auto_now fields automatically in some Django versions? 
        # Actually it does NOT update auto_now fields if they are not in update_fields.
        # So we should include 'updated_at' if we want it updated, but Order model has auto_now=True for updated_at.
        # To be safe and simple, just save().
        order.save(update_fields=['total_amount', 'updated_at'])
