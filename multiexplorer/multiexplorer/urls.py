from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import TemplateView

from views import (
    home, perform_lookup, single_address, block_lookup, api_docs, address_disambiguation,
    onchain_exchange_rates, onchain_status, logout, single_tx, handle_memo, serve_memo_pull,
    historical_price, plot_supply, test, paper_wallet, crypto_data_page, replay_attack
)

admin.site.site_header = 'MultiExplorer Administration'

urlpatterns = [
    # Examples:
    # url(r'^$', 'multiexplorer.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', home, name="home"),

    url(r'^address/(?P<address>\w+)/$', single_address, name="single_address"),
    url(r'^block', block_lookup, name="block_lookup"),
    url(r'^tx/(?P<crypto>\w{3,5})/(?P<txid>\w+)', single_tx, name="single_tx"),

    url(r'^api$', api_docs, name="api_docs"),
    url(r'^api/onchain_exchange_rates', onchain_exchange_rates, name="onchain_exchange_rates"),
    url(r'^api/onchain_exchange_status', onchain_status, name="onchain_status"),

    url(r'^api/historical_price', historical_price, name="historical_price"),
    url(r'^api/(?P<service_mode>\w+)/(?P<service_id>\w+)', perform_lookup, name="perform_lookup"),

    url(r'^disambiguation/(?P<address>\w+)', address_disambiguation, name="address_disambiguation"),

    url(r'^wallet/', include('wallet.urls')),
    url(r'^exchange/', include('exchange.urls')),
    url(r'^paper_wallet/', paper_wallet, name="paper_wallet"),
    url(r'^crypto_data/(?P<path1>[\w-]+)/(?P<path2>[\w-]+)', crypto_data_page, name="crypto_data"),
    url(r'^crypto_data/', crypto_data_page, name="crypto_data"),
    url(r'^replay_attack/(?P<fork_coin>\w{2,5})/(?P<block_to_replay>\d+)', replay_attack, name="replay_attack"),
    url(r'^replay_attack/', replay_attack, name="replay_attack"),

    url(r'^memo$', handle_memo),
    url(r'^memo/pull$', serve_memo_pull),

    url(r'graphs/supply', plot_supply),

    url(r'^logout/', logout, name="logout"),

    url(r'^test/', test, name="test"),
]


from django.conf import settings

if settings.DEBUG:
    from django.core.handlers.base import BaseHandler

    handle_uncaught_exception = BaseHandler.handle_uncaught_exception

    def _handle_uncaught_exception_monkey_patch(self, request, resolver, exc_info):
        if settings.DEBUG:
            request.is_ajax = lambda: False

        return handle_uncaught_exception(self, request, resolver, exc_info)

    BaseHandler.handle_uncaught_exception = _handle_uncaught_exception_monkey_patch
