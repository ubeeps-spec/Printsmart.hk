import os
import django
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eshop.settings')
django.setup()

from store.models import PaymentMethod

def run():
    methods = [
        {
            'name': '銀行轉帳 (Bank Transfer)',
            'code': 'bank_transfer',
            'description': '請將款項匯入以下銀行帳戶，並上傳入數紙。',
            'instructions': '<p><strong>銀行名稱:</strong> HSBC 匯豐銀行<br><strong>帳戶號碼:</strong> 123-456-789<br><strong>戶名:</strong> PrintSmart HK Ltd.</p>',
            'requires_proof': True,
            'is_active': True
        },
        {
            'name': '轉數快 (FPS)',
            'code': 'fps',
            'description': '使用 FPS 轉數快付款，方便快捷。',
            'instructions': '<p><strong>FPS ID:</strong> 1234567<br><strong>電話:</strong> 98765432</p>',
            'requires_proof': True,
            'is_active': True
        },
        {
            'name': 'PayMe',
            'code': 'payme',
            'description': '使用 PayMe 付款。',
            'instructions': '<p>請掃描以下 QR Code 付款 (模擬)：<br><a href="#">[PayMe Link]</a></p>',
            'requires_proof': True,
            'is_active': True
        },
        {
            'name': '信用卡 (Credit Card)',
            'code': 'credit_card',
            'description': '使用信用卡線上付款，系統自動確認付款。',
            'instructions': '<p>目前為測試流程：選擇信用卡後，訂單將視為已付款並進入出貨流程。</p>',
            'requires_proof': False,
            'is_active': True
        },
        {
            'name': '貨到付款 (Cash on Delivery)',
            'code': 'cod',
            'description': '送貨時直接支付現金。',
            'instructions': '<p>請準備準確的現金金額，司機不設找贖。</p>',
            'requires_proof': False,
            'is_active': True
        }
    ]

    for data in methods:
        pm, created = PaymentMethod.objects.update_or_create(
            code=data['code'],
            defaults={
                'name': data['name'],
                'description': data['description'],
                'instructions': data['instructions'],
                'requires_proof': data['requires_proof'],
                'is_active': data['is_active']
            }
        )
        if created:
            print(f"Created payment method: {pm.name}")
        else:
            print(f"Updated payment method: {pm.name}")

if __name__ == '__main__':
    run()
