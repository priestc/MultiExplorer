# Memo Server Specification

## What is a Memo?

A memo is a small piece of text written by a crypto-currency user that describes
actions and motivations behind a transaction.

Many wallets these days use deterministic key generation. This allows the wallet user
to easily move their funds from one wallet software provider to another.

Unfortunately not all wallet data can be easily moved over, such as wallet settings,
imported wallets, and memos.

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

If the message is encrypted with the AES algorithm, provided by the [CryptoJS](https://github.com/brix/crypto-js)
library. The encrypted message is then signed with the private key that is returned by
the function `my_privkeys_from_txid`. This function actually returns a list of
private keys, but in the code above only the first one is selected from that list
to be the one we use to create the memo publish request.

The signing algorithm is provided by the project bitcore-message. All default
settings are used.

The resulting signature is sent to the memo server, along with the corresponding
public key, the AES encrypted message, the txid, and the crypto-currency symbol for
the blockchain the TXID is from.

The function `my_privkeys_from_txid` is not defined here. What it does is takes in a
txid, and then calls the correct blockchain and returns the inputs and outputs for that
transaction. The function loops through each input and output, and determines which ones
were made by private keys the wallet controls. This function then returns those
WIF encoded private keys in alphabetical order.

A full memo publish request looks like the following:

    private key: T5wFr74YkSA3ocEkDNHhmEHYsoqF3u2TtYXmNxNVnM2A8EHmK79o

    {
        'currency': 'ltc',
        'encrypted_text': 'U2FsdGVkX18OpKZr/NwOfq/KNi204cyz4voruMKJhaTZ9yYgZTB5TOMRzz35QpWe',
        'pubkey': '0291943324e37bc7902848960d1b52059c958da679c08276700b37c510bd930d11',
        'signature': 'H9Pwm6yDpsPMhLRzxVy4LSSSiAUAmZhDYxy4nkNO2n98fCbudE0NXWB62oYHR/3ndc9a1mcgCK8UUfpKNnRIqmE=',
        'txid': '2b9ae1249c9330fa1ad0005afc3c962795d71f46540d626965bd04f0df1b5d7a'
    }

## Front end memo decrypt

```javascript
function decrypt_memo(crypto, txid, encrypted_memos) {
    // given a list of encrypted memos and a txid, decrypt each one
    // and return the result as soon as one is found.
    var my_keys = my_privkeys_from_txid(crypto, txid);
    var match = undefined;
    $.each(encrypted_memos, function(i, encrypted_memo) {
        $.each(my_keys, function(i, priv){
            var decrypted_attemp = CryptoJS.AES.decrypt(encrypted_memo, priv).toString(CryptoJS.enc.Utf8);
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

The AES decrypt function is provided by the [CryptoJS](https://github.com/brix/crypto-js) library. The memo server may
return multiple encrypted memos per txid, so we have to loop over each one and
attempt to decrypt each obe until we get a match. We know we have a match when
the first six letters of the result are "BIPXXX".

## Server side save

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
## Server side get by txid

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
                return http.HttpResponse(
                    "TXID: %s is too small. Must include 4 chars." % txid, status_code=400
                )
            q = q | Q(txid__startswith=txid)

        memos = memos.filter(q)

    else:
        memos = memos.filter(txid__startswith=txid)

    return http.JsonResponse({'memos':
        [{'txid':x.txid, 'memo': x.encrypted_text} for x in memos]
    })
```
