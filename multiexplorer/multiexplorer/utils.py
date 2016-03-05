import json
from moneywagon.crypto_data import crypto_data
from moneywagon import ALL_SERVICES

service_modes = [
    'current_price', 'address_balance', 'historical_transactions', 'push_tx',
    'unspent_outputs', 'get_block', 'get_optimal_fee'
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
