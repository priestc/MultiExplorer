# Memo Server Specification

## What is a Memo?

A memo is a small piece of text written by a crypto-currency user that describes
actions and motivations behind a transaction.

Many wallets these days use deterministic key generation. This allows the wallet user
to easily move their funds from one wallet software provider to another.

Unfortunately not all wallet data can be easily moved over, such as wallet settings,
imported wallets, and memos.

This system creates a decentralized network of "memo servers" that store encrypted memos.
When users move their master seed from one wallet that supports Memo server, to another
wallet that supports memo server, they memos will carry over to the new wallet.

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

The signing algorithm is provided by the project [bitcore-message](https://github.com/bitpay/bitcore-message). All default
settings are used.

The resulting signature is sent to the memo server, along with the corresponding
public key, the AES encrypted message, the txid, and the crypto-currency symbol for
the blockchain the TXID is from.

The function `my_privkeys_from_txid` is not defined here. What it does is takes in a
txid, and then calls the correct blockchain and returns the inputs and outputs for that
transaction. The function loops through each input and output, and determines which ones
were made by private keys the wallet controls. This function then returns those
WIF encoded private keys in alphabetical order.

To see the entire implementatin of the `my_privkeys_from_txid` function, refer
to the [MultiExplorer code on github](https://github.com/priestc/MultiExplorer/blob/716a17b159e1fe2e99ee9bf5bcd5461860a71f68/multiexplorer/wallet/static/wallet.js#L918)

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
attempt to decrypt each one until we get a match. We know we have a match when
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

    tx = get_transaction(crypto, txid=txid)

    address = pubkey_to_address(pubkey, crypto)
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

* Lines 2-6: Variables are set based on data sent in from the POST body
* Lines 8-12: The memo is checked to make sure it isn't greater than the max
length determined by the memo server settings.
* Lines 14-15: If this memo server already has this exact memo already stored in it's
database, nothing is done. This prevents a "push loop" from occurring.
* Lines 17: The TXID is retrieved from a database of blockchain data.
* Lines 19-24: The Pubkey is converted to an address, and then the address is verified to
exist within one of the inputs of outputs. If the addresses is not found, an error
response is returned. If the address is found, execution continues.
* Lines 26-34: The signature is verified to be valid, using the `pubkey`, and `encrypted_text`.
If the signature is found to be valid, the memo is saved. Otherwise an error
response is returned. If there is already a memo in the server with the same TXID and
pubkey, this new memo will replace the old one.
* Line 38: The text "OK" is returned if the memo publish was completed successfully.

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

# Push and Pulling

Memo servers can push and pull memos between each other. A memo server can
also run in "private mode", which will disable all push and pull operations.
