bip44_coin_types = {};
$.each(crypto_data, function(i, data) {
    var network = {};
    network.alias = data['code'];
    network.name = data['name'];
    network.pubkeyhash = data['address_byte'];
    bip44_coin_types[data['code']] = data['bip44'];
    bitcore.Networks.add(network);
});

function get_deposit_address(crypto, index) {
    var bip44_coin_type = undefined;
    var address_byte = undefined;
    var network = bitcore.Networks.get(crypto);
    var bip44 = bip44_coin_types[crypto];
    var xpriv = hd_master_seed.derive(44, true).derive(bip44).derive(index)
    return xpriv.privateKey.toAddress(crypto);
}
