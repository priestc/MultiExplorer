var bip44_coin_types = {};
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

function arrayRotate(arr, reverse){
    // taken from http://stackoverflow.com/a/23368052/118495
    if(reverse)
        arr.unshift(arr.pop());
    else
        arr.push(arr.shift());
    return arr;
}

function get_crypto_root(crypto) {
    var bip44_coin_type = undefined;
    var address_byte = undefined;
    var bip44 = bip44_coin_types[crypto];

    if(crypto == 'btc') {
        crypto = 'livenet';
    }
    //                         purpose       coin type
    return hd_master_seed.derive(44, true).derive(bip44);
}

function derive_addresses(xpriv, crypto, change, index) {
    //           account             change             index
    xpriv = xpriv.derive(0, true).derive(change ? 1 : 0).derive(index);

    if(crypto == 'btc') {
        crypto = 'livenet';
    }

    var wif = bitcore.PrivateKey(xpriv.privateKey.toString(), crypto).toWIF();
    return [wif, xpriv.privateKey.toAddress(crypto).toString()];
}

function get_deposit_keypair(crypto, index) {
    return derive_addresses(get_crypto_root(crypto), crypto, false, index);
}

function get_change_keypair(crypto, index) {
    return derive_addresses(get_crypto_root(crypto), crypto, true, index);
}

function fetch_used_addresses(crypto, callback, blank_length, skip_addresses) {
    // iterates through the deposit chain until it finds 20 blank addresses.

    var addresses = [];
    var i = 0;
    while(addresses.length < blank_length) {
        var gen = get_deposit_keypair(crypto, i)[1];
        if(skip_addresses.indexOf(gen) == -1) {
            addresses.push(gen);
        }
        i += 1;
    }

    var addresses_with_activity = [];
    var args = "?addresses=" + addresses.join(",") + "&currency=" + crypto;
    $.ajax({
        'url': "/api/historical_transactions/private5" + args,
        'type': 'get',
    }).success(function (response) {
        $.each(response['txs'], function(i, tx) {
            $.each(tx.addresses, function(i, address) {
                var not_already_marked = addresses_with_activity.indexOf(address) == -1;
                if(not_already_marked) {
                    addresses_with_activity.push(address);
                }
            });
        });
        console.log("after ajax", addresses_with_activity, crypto);
        var all_used = addresses_with_activity.concat(skip_addresses);
        var needs_to_go = addresses_with_activity.length;
        if(needs_to_go <= 0) {
            // all results returned no activity
            callback(all_used);
            console.log("finished callback for", crypto);
        } else {
            console.log("another ajax", crypto);
            fetch_used_addresses(crypto, callback, needs_to_go, all_used);
        }
    });
}

function rotate_deposit(crypto, up) {
    var pool = unused_deposit_addresses[crypto];
    unused_deposit_addresses[crypto] = arrayRotate(pool, up);
    return pool[0][1];

}

var unused_deposit_addresses = {}
function open_wallet() {
    $("#register_box, #login_box").hide();
    $("#loading_screen").show();
    console.log("start");

    $.each(crypto_data, function(i, data) {
        var crypto = data.code;
        var box = $(".crypto_box[data-currency=" + crypto + "]");

        fetch_used_addresses(crypto, function(used_addresses) {
            var i = 0;
            var deposit_address_pool = [];
            while(deposit_address_pool.length < 5) {
                var gen = get_deposit_keypair(crypto, i);
                var not_used = used_addresses.indexOf(gen) == -1;
                var not_already_added = deposit_address_pool.indexOf(gen) == -1;
                if(not_used && not_already_added) {
                    // If newly generated address has not already been used,
                    // add it to the pool. Otherwise generate another and check again.
                    deposit_address_pool.push(gen);
                }
                i += 1;
            }
            unused_deposit_addresses[crypto] = deposit_address_pool;
            var address = deposit_address_pool[0][1];
            box.find(".deposit_address").text(address);
            box.find(".qr").empty().qrcode({render: 'div', width: 100, height: 100, text: address});

            if(used_addresses.length == 0) {
                box.find(".crypto_balance").text("0.0");
            } else {
                calculate_balance(used_addresses);
            }
        }, 10, []);

        box.find(".deposit_shift_down").click(function() {
            var address = rotate_deposit(crypto, true);
            box.find(".deposit_address").text(address);
            box.find(".qr").empty().qrcode({render: 'div', width: 100, height: 100, text: address});
        });
        box.find(".deposit_shift_up").click(function() {
            var address = rotate_deposit(crypto, false);
            box.find(".deposit_address").text(address);
            box.find(".qr").empty().qrcode({render: 'div', width: 100, height: 100, text: address});
        });
    });

    $("#loading_screen").hide();
    $("#wallets").show();
    console.log('end');
}
