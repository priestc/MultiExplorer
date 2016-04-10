from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import TemplateView

from views import (
    home, perform_lookup, single_address, block_lookup, api_docs, address_disambiguation
)

urlpatterns = [
    # Examples:
    # url(r'^$', 'multiexplorer.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', home, name="home"),

    url(r'^address/(?P<address>\w+)/$', single_address, name="single_address"),
    url(r'^block', block_lookup, name="block_lookup"),

    url(r'^api$', api_docs, name="api_docs"),
    url(r'^api/(?P<service_mode>\w+)/(?P<service_id>\w+)', perform_lookup, name="perform_lookup"),

    url(r'^disambiguation/(?P<address>\w+)', address_disambiguation, name="address_disambiguation"),
]
