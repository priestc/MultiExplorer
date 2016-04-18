bip44_coin_types = {};
$.each(crypto_data, function(i, data) {

    var network = {};
    network.alias = data['code'];
    network.name = data['name'];
    network.pubkeyhash = data['address_byte'];
    network.privatekey = data['private_key_prefix'];
    bip44_coin_types[data['code']] = data['bip44'];

    if(data['code'] != 'btc') {
        bitcore.Networks.add(network);
    }
});

function get_deposit_address(crypto, change, index) {
    var bip44_coin_type = undefined;
    var address_byte = undefined;
    var bip44 = bip44_coin_types[crypto];

    if(crypto == 'btc') {
        crypto = 'livenet';
    }

    var network = bitcore.Networks.get(crypto);
    var xpriv = hd_master_seed.derive(44, true) //purpose

    //           coin type       account             change             index
    xpriv = xpriv.derive(bip44).derive(1, true).derive(change ? 1 : 0).derive(index);
    var wif = bitcore.PrivateKey(xpriv.privateKey.toString(), crypto).toWIF();
    return [wif, xpriv.privateKey.toAddress(crypto).toString()]
}
