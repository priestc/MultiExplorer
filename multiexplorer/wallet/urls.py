from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import TemplateView

try:
    from views import home, register_new_wallet_user, login, save_settings
except ImportError:
    from .views import home, register_new_wallet_user, login, save_settings

urlpatterns = [
    url(r'^$', home, name="wallet"),
    url(r'^register_new_wallet_user', register_new_wallet_user,
        name="register_new_wallet_user"),
    url(r'^login', login, name='login'),
    url(r'^save_settings', save_settings, name="save_wallet_settings"),
]
