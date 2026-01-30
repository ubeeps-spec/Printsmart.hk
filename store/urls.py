from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('shop/', views.product_list, {'is_shop': True}, name='shop'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('coupon/apply/', views.coupon_apply, name='coupon_apply'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/success/<int:order_id>/', views.order_success, name='order_success'),
    path('order/invoice/<int:order_id>/', views.invoice_view, name='invoice_view'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/order/<int:order_id>/', views.user_order_detail, name='user_order_detail'),
    path('contact/', views.contact_view, name='contact'),
    path('tutorial/', views.tutorial, name='tutorial'),
    path('pages/<slug:slug>/', views.page_detail, name='page_detail'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/', views.toggle_wishlist, name='toggle_wishlist'),
]
