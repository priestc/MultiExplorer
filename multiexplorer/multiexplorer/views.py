import json
import time
import random
import datetime

import arrow
from django.views.decorators.csrf import csrf_exempt
from django import http
from django.template.response import TemplateResponse
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.conf import settings
from django.contrib.auth import logout as dj_logout
import requests

from moneywagon import (
    service_table, get_address_balance, guess_currency_from_address, ALL_SERVICES,
    get_unspent_outputs, get_historical_transactions, get_optimal_fee, get_block,
    get_single_transaction, get_current_price, push_tx
)

from moneywagon.crypto_data import crypto_data
from moneywagon.supply_estimator import SupplyEstimator

from .utils import (
    make_crypto_data_json, make_service_info_json, service_modes,
    get_block_currencies, get_balance_currencies, get_paper_wallet_currencies
)

from .models import CachedTransaction, Memo
from pricetick.models import PriceTick
from bitcoin import ecdsa_verify, pubkey_to_address

services_by_id = {s.service_id: s for s in ALL_SERVICES}
crypto_data_json = make_crypto_data_json()
service_info_json = make_service_info_json()
block_info_currencies = get_block_currencies()
service_table_html = service_table(format='html')

@csrf_exempt
def perform_lookup(request, service_mode, service_id):
    """
    Passes on this request to the API, then return their response normalized to
    a single API. service_mode == (address_balance, historical_transactions)
    """
    include_raw = request.GET.get('include_raw', False)

    extended_fetch = (
        request.GET.get('extended_fetch', 'false').lower() == 'true' and
        service_mode == 'historical_transactions'
    )

    paranoid = service_id.startswith("paranoid")
    average_mode = service_id.startswith("average")
    private_mode = service_id.startswith("private")
    random_mode = False

    if service_id == "random":
        service_id = "fallback"
        random_mode = True

    if service_id == "fallback" or paranoid or average_mode or private_mode:
        Service = None
    else:
        try:
            Service = services_by_id[int(service_id)]
        except IndexError:
            return http.JsonResponse({
                'error': "Unknown Service ID: %s. This service may have been decomissioned." % service_id
            }, status=400)

    address = request.GET.get('address', None)
    addresses = request.GET.get('addresses', [])
    xpub = request.GET.get('xpub', None)
    fiat = request.GET.get('fiat', None)
    txid = request.GET.get('txid', None)

    block_args = {
        'latest': request.GET.get('latest', ''),
        'block_hash': request.GET.get("block_hash", ''),
        'block_number': request.GET.get("block_number", '')
    }

    currency = request.GET.get("currency", None)
    if service_mode == 'push_tx':
        currency = request.POST['currency']

    if not currency:
        try:
            guess_currency_result = guess_currency_from_address(address)
        except ValueError as exc:
            return http.JsonResponse({'error': str(exc)}, status=400)

        if len(guess_currency_result) == 1:
            currency, currency_name = guess_currency_result[0]
        else:
            msg = "Address may be one of %s, please specify which one by using the `currency` parameter" % (
                ', '.join([x[0] for x in guess_currency_result])
            )
            return http.JsonResponse({'error': msg}, status=400)
    else:
        currency_name = crypto_data[currency]['name']
        currency = currency.lower()

    if not currency:
        return http.JsonResponse({
            'error': "Currency Not Recognized: %s" % currency_name
        }, status=400)

    if service_mode == 'push_tx': # don't go inside cache function
        try:
            result = push_tx(currency, request.POST['tx'])
            return http.JsonResponse({
                'txid': result
            })
        except Exception as exc:
            return http.JsonResponse({
                'error': "%s: %s" % (exc.__class__.__name__, str(exc))
            }, status=500)

    errors, response_dict = _cached_fetch(**locals())
    if errors:
        return http.JsonResponse(response_dict, status=500)

    return http.JsonResponse(response_dict)

def make_cache_key(service_mode, a):
    """
    'a' is a dict that contains all the data that can be used to make the key.
    """
    if service_mode == 'optimal_fee':
        return "OF-%s-%s" % (a['service_id'], a['currency'])

    if service_mode == 'get_block':
        return "GB-%s-%s-%s" % (
            a['service_id'], a['currency'], ','.join(a['block_args'].values())
        )

    if service_mode == 'current_price':
        return "CP-%s-%s-%s" % (
             a['service_id'], a['currency'], a['fiat'],
        )

    if service_mode in ['address_balance', 'unspent_outputs', 'historical_transactions'] :
        add = a.get('addresses') or a['address']
        addresses = (','.join([x[:5] for x in add.split(',')]))
        ef = "-EF" if a.get('extended_fetch') else ""
        return "%s-%s-%s-%s%s" % (
            service_mode, a['service_id'], a['currency'], addresses, ef
        )

    if service_mode == 'single_transaction':
        return "ST-%s-%s-%s-%s" % (
            a['service_id'], a['currency'], a['txid'][:8], a['fiat']
        )


def _cached_fetch(service_mode, service_id, address=None, addresses=None, xpub=None,
    currency=None, currency_name=None, fiat=None, include_raw=False, Service=None, block_args=None,
    extended_fetch=False, txid=None, random_mode=False, **k):

    cache_key = make_cache_key(service_mode=service_mode, a=locals())
    hit = cache.get(cache_key)
    #print "cache key", cache_key

    if hit:
        response_dict = hit
    else:
        if settings.DEBUG:
            # let error occur, preserving the traceback
            to_catch = None
        else:
            # catch any error and return message to front end to show the user
            to_catch = Exception

        try:
            response_dict = _make_moneywagon_fetch(**locals())
            if extended_fetch:
                response_dict = _do_extended_fetch(currency, response_dict['transactions'], fiat)
        except to_catch as exc:
            return True, {'error': "%s: %s" % (exc.__class__.__name__, str(exc))}

        response_dict.update({
            'timestamp': int(time.time()),
            'currency': [currency, currency_name]
        })

        if not service_mode == 'single_transaction':
            cache.set(cache_key, response_dict)

    if not include_raw:
        response_dict.pop('raw_response', None)
        services = response_dict.get('services', [])
        if services:
            response_dict['services'] = [
                {'name': x['name'], 'id': x['id']} for x in services
            ]

    response_dict['fetched_seconds_ago'] = int(time.time()) - response_dict['timestamp']
    del response_dict['timestamp']
    return None, response_dict


def _make_moneywagon_fetch(Service, service_mode, service_id, address, addresses,
    xpub, currency, currency_name, block_args, fiat=None, txid=None, random_mode=False, **k):

    if Service:
        if Service.supported_cryptos and currency not in Service.supported_cryptos:
            raise Exception("%s not supported for %s with %s" % (
                currency_name, service_mode, Service.name
            ))
        services = [Service]
    else:
        services = [] # fallback mode

    modes = dict(
        report_services=True,
        services=services,
        random=random_mode,
        timeout=10.0
    )

    if service_id.startswith("paranoid"):
        modes['paranoid'] = int(service_id[8:])
    elif service_id.startswith("average"):
        modes['average'] = int(service_id[7:])
    elif service_id.startswith("private"):
        modes['private'] = int(service_id[7:])
        if modes['private'] > 30:
            raise Exception("Private mode maximum of 30")

    if address:
        modes['address'] = address
    elif addresses:
        modes['addresses'] = addresses.split(',')

    if service_mode == 'current_price':
        used_services, price = get_current_price(currency, fiat, **modes)
        PriceTick.record_price(price, currency, fiat, used_services[0].name)
        ret = {'current_price': price}
    elif service_mode == 'address_balance':
        used_services, balance = get_address_balance(currency, **modes)
        ret = {'balance': balance}
    elif service_mode == 'unspent_outputs':
        used_services, utxos = get_unspent_outputs(currency, **modes)
        ret = {'utxos': sorted(utxos, key=lambda x: x['output'])}
    elif service_mode == 'historical_transactions':
        used_services, txs = get_historical_transactions(currency, **modes)
        ret = {'transactions': sorted(txs, key=lambda x: x['txid'])}
    elif service_mode == 'single_transaction':
        used_services = None
        tx = CachedTransaction.fetch_full_tx(currency, txid=txid, fiat=fiat)
        ret = {'transaction': tx}
    elif service_mode == 'get_block':
        if block_args['block_number']:
            block_args['block_number'] = int(block_args['block_number'])
        modes.update(block_args)
        used_services, block_data = get_block(currency, **modes)
        ret = {'block': block_data}
    elif service_mode == 'optimal_fee':
        used_services, fee = get_optimal_fee(currency, 1024, **modes)
        ret = {'optimal_fee_per_KiB': fee}
    else:
        raise Exception("Unsupported Service mode")

    if not used_services:
        pass # private mode does not return services
    elif len(used_services) == 1:
        s = used_services[0]
        if s:
            ret['url'] = s.last_url
            ret['raw_response'] = s.last_raw_response.json()
            ret['service_name'] = s.name
            ret['service_id'] = s.service_id
    else:
        ret['services'] = [
            {'name': s.name, 'id': s.service_id, 'raw_response': s.last_raw_response.json()}
            for s in used_services
        ]

    return ret

def _do_extended_fetch(crypto, transactions, fiat=None):
    """
    `transactions` is a list of transactions that comes from get_historical_transactions
    Sometimes there will be a confirmations attribute, sometimes not (depending on which
    service was used).
    """
    txs = []
    for tx in transactions:
        full_tx = CachedTransaction.fetch_full_tx(
            crypto, txid=tx['txid'], fiat=fiat
        )
        if full_tx:
            # if fetch_full_tx returns None, it means another thread is in the process
            # of getting that txid, so ignore here.
            txs.append(full_tx)

    return {'transactions': txs}


def home(request):
    return TemplateResponse(request, "home.html", {
        'supported_currencies': get_balance_currencies,
        'block_info_currencies': block_info_currencies,
    })


def single_address(request, address):
    currency = request.GET.get('currency', None)

    if not currency:
        try:
            guess_currency_result = guess_currency_from_address(address)
        except Exception as exc:
            return TemplateResponse(request, "single_address.html", {
                'crypto_data_json': crypto_data_json,
                'service_info_json': service_info_json,
                'address': address,
                'currency': None,
                'transactions': [],
                'currency_name': None,
                'currency_icon': None,
            })

        if len(guess_currency_result) == 1:
            currency, currency_name = guess_currency_result[0]
        else:
            return http.HttpResponseRedirect(
                reverse("address_disambiguation", kwargs={'address': address})
            )
    else:
        currency = currency.lower()
        crypto_name = currency_name = crypto_data[currency]['name']

    error, response = _cached_fetch(
        currency=currency, currency_name=currency_name, service_id="fallback",
        address=address, Service=None, service_mode="historical_transactions"
    )

    if not error:
        txs = response['transactions']
    else:
        txs = []

    return TemplateResponse(request, "single_address.html", {
        'crypto_data_json': crypto_data_json,
        'service_info_json': service_info_json,
        'address': address,
        'currency': currency,
        'transactions': txs,
        'currency_name': currency_name,
        'currency_icon': "logos/" + currency.lower() + "-logo.png",
    })


def block_lookup(request):
    return TemplateResponse(request, "block_lookup.html", {
        'crypto_data_json': crypto_data_json,
        'service_info_json': service_info_json,
        'block_info_currencies': block_info_currencies,
        'currency': request.GET.get('currency', None),
        'block_hash': request.GET.get("block_hash", None),
        'block_number': request.GET.get("block_number", None)
    })


def api_docs(request):
    return TemplateResponse(request, 'api_docs.html', {
        'service_table': service_table_html,
        'domain': settings.ALLOWED_HOSTS[0],
    })

def address_disambiguation(request, address):
    """
    When the user tried to lookup a currency that has a duplicate address byte
    take them to this page where they can choose which currency they meant.
    """
    guess_currency_result = guess_currency_from_address(address)
    balances = {}
    for crypto, name in guess_currency_result:
        try:
            balance = get_address_balance(crypto, address)
        except Exception as exc:
            balance = str(exc)

        balances[crypto.upper()] = {'balance': balance, 'name': name}

    return TemplateResponse(request, "address_disambiguation.html", {
        'balances': balances,
        'address': address,
    })

def onchain_exchange_rates(request):
    """
    Returns a list of exchange pairs that are supported by all onchain exchange services.
    (currently only shapeshift.io is supported). After a second onchain exchange is defined,
    this code will be moved to moneywagon.
    """
    cache_key = 'shapeshift_marketinfo'
    hit = cache.get(cache_key)

    if not hit:
        pairs = requests.get("https://shapeshift.io/marketinfo/").json()
        cache.set(cache_key, pairs)
    else:
        pairs = hit

    deposit_currency = request.GET.get('deposit_currency', '').upper()
    final_pairs = []

    for pair in pairs:
        if deposit_currency and not pair['pair'].startswith(deposit_currency):
            continue

        deposit_code = pair['pair'].split("_")[0]
        try:
            deposit_name = crypto_data[deposit_code.lower()]['name']
        except (KeyError, TypeError):
            continue

        withdraw_code = pair['pair'].split("_")[1]

        try:
            withdraw_name = crypto_data[withdraw_code.lower()]['name']
        except (KeyError, TypeError):
            continue

        if pair['maxLimit'] == 0:
            continue

        final_pairs.append({
            'deposit_currency': {'code': deposit_code, 'name': deposit_name},
            'withdraw_currency': {'code': withdraw_code, 'name': withdraw_name},
            'rate': pair['rate'],
            'max_amount': pair['maxLimit'],
            'min_amount': pair['min'],
            'withdraw_fee': pair['minerFee'],
            'provider': 'ShapeShift.io'
        })


    return http.JsonResponse({'pairs': final_pairs})

def logout(request):
    dj_logout(request)
    return http.HttpResponseRedirect("/")

def onchain_status(request):
    deposit_crypto = request.GET['deposit_currency']
    address = request.GET['address']

    response = requests.get("https://shapeshift.io/txStat/" + address).json()
    return http.JsonResponse(response)

def single_tx(request, crypto, txid):
    full_tx = CachedTransaction.fetch_full_tx(crypto, txid=txid, fiat='usd')
    hist_price = full_tx['historical_price'] or 0
    if hist_price:
        hist_price = hist_price['price']
    fee = full_tx['fee'] / 1e8
    full_tx['fee'] = "%.8f %s (%.2f USD)" % (fee, crypto.upper(), fee * hist_price)
    s = full_tx['size']
    full_tx['size'] = "%.2f KB" % (s / 1024.0) if s > 1024 else "%d bytes" % s

    ins = []
    for x in full_tx['inputs']:
        amount = x['amount'] / 1e8
        ins.append({
            'txid': x['txid'],
            'amount': "%.8f %s (%.2f USD)" % (amount, crypto.upper(), hist_price * amount)
        })

    full_tx['inputs'] = ins

    outs = []
    for x in full_tx['outputs']:
        amount = x['amount'] / 1e8
        outs.append({
            'address': x['address'],
            'amount': "%.8f %s (%.2f USD)" % (amount, crypto.upper(), hist_price * amount)
        })

    full_tx['outputs'] = outs

    return TemplateResponse(request, "single_transaction.html", {
        'tx': full_tx,
        'crypto': crypto,
        'crypto_name': crypto_data[crypto]['name']
    })

@csrf_exempt
def handle_memo(request):
    if request.POST:
        return save_memo(request)
    if request.GET:
        return get_memo(request)

def save_memo(request):
    encrypted_text = request.POST['encrypted_text']
    pubkey = request.POST['pubkey']
    sig = request.POST['signature']
    txid = request.POST['txid'].lower()
    crypto = request.POST.get('currency', 'btc').lower()

    if len(encrypted_text) > settings.MAX_MEMO_SIZE_BYTES:
        return http.JsonResponse(
            {'error': "Memo exceeds maximum size of: %s bytes" % settings.MAX_MEMO_SIZE_BYTES},
            status=400
        )

    data = dict(pubkey=pubkey, crypto=crypto, txid=txid, encrypted_text=encrypted_text)
    if Memo.objects.filter(**data).exists():
        return http.HttpResponse("OK")
    data['signature'] = sig

    try:
        version_byte = crypto_data[crypto]['address_version_byte']
    except IndexError:
        return http.HttpResponse("Currency not supported", status=400)

    address = pubkey_to_address(pubkey, version_byte)
    tx = CachedTransaction.fetch_full_tx(crypto, txid=txid)

    for item in tx['inputs'] + tx['outputs']:
        if item['address'] == address:
            break
    else:
        return http.HttpResponse("Pubkey not in TXID", status=400)

    if ecdsa_verify(encrypted_text, sig, pubkey):
        memo, c = Memo.objects.get_or_create(
            crypto=crypto,
            txid=txid,
            pubkey=pubkey
        )
        memo.encrypted_text = encrypted_text
        memo.signature = sig
        memo.save()
    else:
        return http.HttpResponse("Invalid signature", status=400)

    return http.HttpResponse("OK")

def get_memo(request):
    """
    Given a txid, or a list of txids, return all memos that match the txid.
    Can pass in either full txids, or "first bits" of at least 4 chars.
    """
    crypto = request.GET.get('currency', 'btc').lower()
    txid = request.GET.get('txid')
    memos = Memo.objects.filter(crypto=crypto).exclude(encrypted_text="Please Delete")

    if ',' in txid:
        txids = txid.split(',')
        q = Q()
        for txid in txids[:50]:
            if len(txid) < 4:
                return http.JsonResponse("TXID: %s is too small. Must include 4 chars." % txid)
            q = q | Q(txid__startswith=txid)

        memos = memos.filter(q)

    else:
        memos = memos.filter(txid__startswith=txid)

    return http.JsonResponse({'memos':
        [{'txid':x.txid, 'memo': x.encrypted_text} for x in memos]
    })

def serve_memo_pull(request):
    """
    There are two ways to use the "Memo Pull" method: by eithr pasing in a "since timestamp",
    or by passing in a page number.

    Page number is used when performing a "full memo sync", and does not include
    records of deleted memos.

    On the other hand, "since timestamp" is used when performing a periodical
    pull. The response will include all new memos (and "Please Delete" memos)
    made since the timestamp.
    """
    if settings.MEMO_SERVER_PRIVATE_MODE:
        return http.HttpResponse("Memo Server is in Private Mode", status=401)

    if request.GET.get('since'):
        since = arrow.get(request.GET['since'])
        memos = Memo.objects.filter(created__gte=since.datetime).order_by('created')

    if request.GET.get('page'):
        start = (int(request.GET.get('page', 1)) - 1) * 100
        end = start + 100
        memos = Memo.objects.exclude(encrypted_text="Please Delete").order_by('created')[start:end]

    return http.JsonResponse({'memos': [{
        't': m.encrypted_text,
        'p': m.pubkey,
        'x': m.txid,
        'c': m.crypto,
        } for m in memos
    ]})

def historical_price(request):
    fiat = request.GET['fiat'].upper()
    crypto = request.GET['currency'].upper()
    try:
        time = arrow.get(request.GET['time']).datetime
    except:
        return http.JsonResponse({'error': "Invalid Time argument"}, status=400)

    try:
        price = PriceTick.nearest(crypto, fiat, time)
    except PriceTick.DoesNotExist:
        return http.JsonResponse(
            {'error': "Can't get historical price for %s->%s" % (fiat, crypto)},
            status=400
        )

    try:
        naive_time = time.replace(tzinfo=None)
        price['estimated_supply'] = SupplyEstimator(crypto).calculate_supply(at_time=naive_time)
    except NotImplementedError:
        pass

    price['currency'] = crypto
    return http.JsonResponse(price)

def plot_supply(request):
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.dates import DateFormatter
    currency = request.GET['currency']
    genesis = crypto_data[currency.lower()]['genesis_date']
    currency_name = crypto_data[currency.lower()]['name']
    s = SupplyEstimator(currency)

    try:
        max_block = crypto_data[currency.lower()]['supply_data']['reward_ends_at_block']
        end = s.estimate_date_from_height(max_block)
    except KeyError:
        end = genesis + datetime.timedelta(days=365 * 50)

    x = list(date_generator(genesis, end))
    y = [s.calculate_supply(at_time=z)/1e6 for z in x]

    fig = Figure()
    ax = fig.add_subplot(111)
    ax.plot_date(x, y, '-')

    ax.set_title("%s Supply" % currency_name)
    ax.grid(True)
    ax.xaxis.set_label_text("Date")
    ax.yaxis.set_label_text("%s Units (In millions)" % currency.upper())

    ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()

    canvas = FigureCanvas(fig)
    response = http.HttpResponse(content_type='image/png')
    canvas.print_png(response)
    return response

def date_generator(start, end, step_days=10):
    delta = int((end - start).total_seconds() / (3600 * step_days))
    for x in xrange(0, delta, step_days):
        dd =  start + datetime.timedelta(days=x)
        if dd > end:
            return
        yield dd


def test(request):
    return TemplateResponse(request, "test_template.html")


def paper_wallet(request):
    paper_wallet_currencies = sorted(get_paper_wallet_currencies(), key=lambda x: x['name'])
    paper_wallet_currencies_json = json.dumps(paper_wallet_currencies)
    return TemplateResponse(request, "paper_wallet.html", locals())
