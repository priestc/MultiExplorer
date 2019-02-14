from django.conf.urls import include, url
from django.views.generic import TemplateView

from views import (
    accept_tx, ping, get_peers, network_summary
)

urlpatterns = [
    url(r'^accept_tx/', accept_tx),
    url(r'^ping/', ping),
    url(r'^get_peers/', get_peers),
    url(r'^summary/', network_summary),
]
