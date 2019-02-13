from django.conf.urls import include, url
from django.views.generic import TemplateView

from views import (
    accept_tx, ping, get_peers
)

urlpatterns = [
    url(r'^accept_tx/', accept_tx),
    url(r'^ping/', ping),
    url(r'^get_peers/', get_peers),
]
