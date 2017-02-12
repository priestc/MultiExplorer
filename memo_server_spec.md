# Memo Server Specification

## What is a Memo?

A memo is a small piece of text written by a crypto-currency user that describes
actions and motivations behind a transaction.

Many wallets these days use deterministic key generation. This allows the wallet user
to easily move their funds from one wallet software provider to another.

Unfortunately not all wallet data can be easily moved over, such as wallet settings,
imported wallets, and memos.

## Front end memo decrypt

```javascript
function decrypt_memo(crypto, txid, encrypted_memos) {
    // given a list of encrypted memos and a txid, decrypt each one
    // and return the result as soon as one is found.
    var my_keys = my_privkeys_from_txid(crypto, txid);
    var match = undefined;
    $.each(encrypted_memos, function(i, encrypted_memo) {
        $.each(my_keys, function(i, priv){
            try {
                var decrypted_attemp = CryptoJS.AES.decrypt(encrypted_memo, priv).toString(CryptoJS.enc.Utf8);
            } catch(e) { // sometimes failed decrypts attempts result in UTF8 failures.
                var decrypted_attemp = "";
            }
            if(decrypted_attemp.substr(0, 6) == 'BIPXXX') {
                match = decrypted_attemp.substr(6);
                return false; // stop iteration
            }
        });
        if(match) {
            return false; //stop iteration
        }
    });
    return match;
}
```
## Front end Memo encrypt and publish

```javascript
function save_memo(message, crypto, txid) {
    var priv = my_privkeys_from_txid(crypto, txid)[0];
    if(message) {
        var encrypted_text = CryptoJS.AES.encrypt("BIPXXX" + message, priv).toString();
    } else {
        var encrypted_text = "Please Delete";
    }
    var pk = bitcore.PrivateKey.fromWIF(priv);
    var sig = Message(encrypted_text).sign(pk).toString();

    $.ajax({
        url: "https://multiexplorer.com/memo",
        type: "post",
        data: {
            encrypted_text: encrypted_text,
            signature: sig,
            currency: crypto,
            txid: txid,
            pubkey: pk.toPublicKey().toString()
        }
    })
}
```

# server side save

```python
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

    if Memo.objects.filter(encrypted_text=encrypted_text, txid=txid).exists():
        return http.HttpResponse("OK")

    address = pubkey_to_address(pubkey, crypto)
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
```
# server side get by txid

```python
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
```
