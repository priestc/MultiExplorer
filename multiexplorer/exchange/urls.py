from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import TemplateView

from views import (
    home
)

urlpatterns = [
    url(r'^$', home, name="exchange"),
]
