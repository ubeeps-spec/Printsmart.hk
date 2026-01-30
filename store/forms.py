from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django_recaptcha.fields import ReCaptchaField

class LoginForm(AuthenticationForm):
    captcha = ReCaptchaField()

class RegisterForm(UserCreationForm):
    captcha = ReCaptchaField()
    email = forms.EmailField(required=True, label="Email")

    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("此電子郵件已被註冊")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = user.email  # Set username to email
        if commit:
            user.save()
        return user

class CouponApplyForm(forms.Form):
    code = forms.CharField(label='Coupon', widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Coupon Code'}))

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': '名字',
            'last_name': '姓氏',
            'email': '電子郵件',
        }

from .models import UserProfile

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'address']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'phone': '電話',
            'address': '地址',
        }
