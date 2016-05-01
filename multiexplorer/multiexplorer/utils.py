import datetime
import json
from moneywagon.crypto_data import crypto_data
from moneywagon import ALL_SERVICES
from django.conf import settings

service_modes = [
    'current_price', 'address_balance', 'historical_transactions', 'push_tx',
    'unspent_outputs', 'block_information', 'optimal_fee'
]


def make_service_info_json():
    return json.dumps({
        s.service_id: {'name': s.name, 'url': s.api_homepage} for s in ALL_SERVICES
    })


def make_crypto_data_json():
    """
    Go through all supported cryptocurrencies in moneywagon, and make a
    json encoded object containing all the supported services and magic bytes.
    """
    ret = {}
    for currency, data in crypto_data.items():
        ret[currency] = {}
        if not hasattr(data, 'get') or not currency:
            del ret[currency]
            continue

        ret[currency]['address_version_byte'] = data['address_version_byte']

        for mode in service_modes:
            services = data.get('services', {}).get(mode, [])
            if not services:
                continue
            ret[currency][mode] = [s.service_id for s in services]

        if not ret[currency]:
            # no services defined
            del ret[currency]

    return json.dumps(ret)


def get_block_currencies():
    """
    Returns currencies that have block info services defined.
    """
    ret = []
    for currency, data in crypto_data.items():
        if hasattr(data, 'get') and data.get('services', {}).get("get_block", []):
            ret.append({'code': currency, 'name': data['name']})

    return ret


def get_balance_currencies():
    """
    Returns currencies that have address balance services defined.
    """
    ret = []
    for currency, data in crypto_data.items():
        if hasattr(data, 'get') and data.get('services', {}).get("address_balance", []):
            ret.append({
                'code': currency,
                'name': data['name'],
                'logo': "logos/%s-logo.png" % currency,
            })

    return ret


def get_wallet_currencies():
    """
    Returns currencies that have full wallet functionalities.
    This includes push_tx, a service for getting unspent outputs, and
    a registered BIP44 coin type.
    """
    ret = []
    for currency, data in crypto_data.items():
        if not hasattr(data, 'get'):
            continue

        bip44 = data['bip44_coin_type']
        address_byte = data['address_version_byte']
        priv_byte = data['private_key_prefix']

        services = data.get('services', {})
        pushtx = services.get("push_tx", [])
        unspent = services.get("unspent_outputs", [])

        sc = settings.WALLET_SUPPORTED_CRYPTOS
        is_supported = (not sc) or (currency.lower() in sc)

        if pushtx and unspent and bip44 and priv_byte and is_supported:
            ret.append({
                'code': currency,
                'name': data['name'],
                'bip44': bip44,
                'private_key_prefix': priv_byte,
                'address_byte': address_byte,
                'logo': "logos/%s-logo.png" % currency,
            })

    return ret


def needs_bip44():
    """
    Lists all currencies that have full wallet support from moneywagon, but
    have no defined BIP44 sequence.
    """
    ret = []
    for currency, data in crypto_data.items():
        if not hasattr(data, 'get'):
            continue

        bip44 = data['bip44_coin_type']
        address_byte = data['address_version_byte']
        priv_byte = data['private_key_prefix']

        services = data.get('services', {})
        pushtx = services.get("push_tx", [])
        unspent = services.get("unspent_outputs", [])

        if pushtx and unspent and not bip44 and priv_byte:
            ret.append(currency)

    return ret


def datetime_to_iso(obj):
    """
    Python's default json encoder will blow up when it encounters datetime objects.
    So this work around is needed in order to just handle making datetime
    objects into iso8601 string format.
    """
    if isinstance(obj, datetime.datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError("Type not serializable")
