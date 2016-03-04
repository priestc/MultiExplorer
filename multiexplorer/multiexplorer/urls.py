from django.conf.urls import include, url
from django.contrib import admin
from views import home, perform_lookup

urlpatterns = [
    # Examples:
    # url(r'^$', 'multiexplorer.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', home, name="home"),
    url(r'api/(?P<currency>\w+)/(?P<service_mode>\w+)/(?P<service_id>\w+)', perform_lookup, name="perform_lookup"),
]
