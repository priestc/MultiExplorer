import json
from django.contrib.auth import authenticate, login as init_login
from django.contrib.auth.models import User
from django.template.response import TemplateResponse
from django import http

from .models import WalletMasterKeys
from multiexplorer.utils import get_wallet_currencies

crypto_data_json = json.dumps(get_wallet_currencies())

def home(request):

    seed = None
    if request.user.is_authenticated():
        seed = WalletMasterKeys.objects.get(user=request.user)

    return TemplateResponse(request, "wallet_home.html", {
        'encrypted_seed': seed and seed.encrypted_seed,
        'crypto_data_json': crypto_data_json,
    })


def register_new_wallet_user(request):
    encrypted_wallet_seed = request.POST['encrypted_wallet_seed']

    user = User.objects.create(
        username=request.POST['username'],
        email=request.POST.get('email', ''),
    )
    user.set_password(request.POST['password'])
    user.save()

    WalletMasterKeys.objects.create(
        user=user, encrypted_seed=encrypted_wallet_seed
    )

    return http.HttpResponse("OK")


def login(request):
    username = request.POST['username']
    password = request.POST['password']

    user = authenticate(username=username, password=password)

    if user and user.is_authenticated():
        init_login(request, user)
        seed = WalletMasterKeys.objects.get(user=request.user)

        return http.JsonResponse({
            'encrypted_seed': seed.encrypted_seed,
        })

    return http.HttpResponse("Invalid Login", status=401)
