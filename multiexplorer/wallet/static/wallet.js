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

function get_exchange_rate(crypto) {
    return parseFloat($("#fiat_exchange_rates .rate." + crypto).text());
}

function send_coin(crypto, recipients, fee_rate) {
    var tx = bitcore.Transaction();
}

function calculate_balance(crypto, addresses) {
    // active_deposit_addresses == list of dposit addresses that have acivity
    // these addresses will make up the balance. (plus the change addresses
    // which will be made in another concurrent thread)

    //console.log("calculate balances with:", addresses);

    var box = $(".crypto_box[data-currency=" + crypto + "]");

    if(addresses.length == 1) {
        var a = "?address=" + addresses[0];
        var mode = "fallback";
    } else {
        var a = "?addresses=" + addresses.join(",");
        var mode = "private5";
    }

    $.ajax({
        'url': "/api/address_balance/" + mode + a + "&currency=" + crypto,
        'type': 'get',
    }).success(function (response) {
        //console.log("balance returned", response);
        var bal = box.find(".crypto_balance");
        var existing = parseFloat(bal.text());
        var new_balance = existing + (response.balance.total || response.balance);

        bal.text(new_balance);

        var exchange_rate = get_exchange_rate(crypto);
        //console.log("using fiat exchange rate", exchange_rate, (exchange_rate * new_balance).toFixed(2));
        box.find(".fiat_balance").text((exchange_rate * new_balance).toFixed(2));
    });
}

var optimal_fees = {};
var unused_deposit_addresses = {};
var unused_change_addresses = {};
function fetch_used_addresses(crypto, chain, callback, blank_length, already_tried_addresses, all_used_arg) {
    // iterates through the deposit chain until it finds `blank_length` blank addresses.
    // the last two args are used in iteration, and shoud be passed in empty lists
    // to initialize.
    var all_used = all_used_arg;
    var addresses = [];
    var i = 0;
    while(addresses.length < blank_length) {
        if(chain == 'deposit') {
            var gen = get_deposit_keypair(crypto, i)[1];
        } else if (chain == 'change') {
            var gen = get_change_keypair(crypto, i)[1];
        }
        if(already_tried_addresses.indexOf(gen) == -1) {
            addresses.push(gen);
        }
        i += 1;
    }

    //console.log("making call with addresses:", addresses);

    var addresses_with_activity = [];
    if(addresses.length == 1) {
        var args = "?address=" + addresses[0] + "&currency=" + crypto;
        var mode = "fallback";
    } else {
        var args = "?addresses=" + addresses.join(",") + "&currency=" + crypto;
        var mode = "private5";
    }

    args += "&extended_fetch=true";

    var all_my_addresses = already_tried_addresses.concat(addresses);

    $.ajax({
        'url': "/api/historical_transactions/" + mode + "/" + args,
        'type': 'get',
    }).success(function (response) {
        //console.log("success getting response txs for:", addresses, blank_length);
        $.each(response['transactions'], function(i, tx) {
            //console.log("found tx!", tx);
            var ins_and_outs = tx.inputs.concat(tx.outputs);
            $.each(ins_and_outs, function(i, in_or_out) {
                var address = in_or_out['address'];
                //console.log('trying address', address, all_my_addresses, addresses_with_activity);
                var my_address = all_my_addresses.indexOf(address) >= 0;
                var not_already_marked = addresses_with_activity.indexOf(address) == -1;
                if(my_address && not_already_marked) {
                    //console.log("adding my address to used list:", address);
                    addresses_with_activity.push(address);
                } else {
                    //console.log("not my address, or not adding again:", address)
                }
            });
        });
        //console.log(crypto, 'activity found this round:', addresses_with_activity);
        //console.log(crypto, "pre all_used", all_used);

        var all_tried = addresses.concat(already_tried_addresses);
        all_used = addresses_with_activity.concat(all_used);

        //console.log("all tried", all_tried);
        //console.log(crypto, "all used", all_used);

        var needs_to_go = addresses_with_activity.length;

        //console.log("needs to go", needs_to_go);

        if(needs_to_go == 0) {
            // all results returned no activity

            //console.log("=========== found too many blank addresses", all_tried, all_used)

            var i = 0;
            var unused_address_pool = [];
            while(unused_address_pool.length < 5) {
                if(chain == 'deposit') {
                    var gen = get_deposit_keypair(crypto, i)[1];
                } else if (chain == 'change') {
                    var gen = get_change_keypair(crypto, i)[1];
                }
                var not_used = all_used.indexOf(gen) == -1;
                var not_already_added = unused_address_pool.indexOf(gen) == -1;
                if(not_used && not_already_added) {
                    // If newly generated address has not already been used,
                    // add it to the pool. Otherwise generate another and check again.
                    unused_address_pool.push(gen);
                }
                i += 1;
            }
            if(chain == 'deposit') {
                unused_deposit_addresses[crypto] = unused_address_pool;
            } else if (chain == 'change') {
                unused_change_addresses[crypto] = unused_address_pool;
            }

            //console.log(crypto, 'finished fetch!:', addresses, chain, all_used);
            callback(all_used);
        } else {
            //console.log(crypto, 'recursing:', 'needs to go: 'needs_to_go, 'all tried:', all_tried, 'all_used', all_used);
            fetch_used_addresses(crypto, chain, callback, needs_to_go, all_tried, all_used);
        }
    }).fail(function(jqXHR) {
        var box = $(".crypto_box[data-currency=" + crypto + "]");
        box.find(".deposit_address").css({color: 'red'}).text(jqXHR.responseJSON.error);
    })
}

function rotate_deposit(crypto, up) {
    var pool = unused_deposit_addresses[crypto];
    unused_deposit_addresses[crypto] = arrayRotate(pool, up);
    return pool[0];

}

function open_wallet() {
    $.each(crypto_data, function(i, data) {
        var crypto = data.code;
        var box = $(".crypto_box[data-currency=" + crypto + "]");

        fetch_used_addresses(crypto, 'deposit', function(used_addresses) {
            //console.log(crypto, "======== found deposit addresses:", used_addresses);

            var address = unused_deposit_addresses[crypto][0];
            box.find(".deposit_address").text(address);
            box.find(".qr").empty().qrcode({render: 'div', width: 100, height: 100, text: address});

            if(used_addresses.length == 0) {
                // if the external chain has no activity, then the internal chain
                // must have none either.
                box.find(".crypto_balance").text("0.0");
            } else {
                calculate_balance(crypto, used_addresses);
            }
        }, 10, [], []);

        fetch_used_addresses(crypto, 'change', function(used_addresses) {
            //console.log("used change addresses", used_addresses);
            if(used_addresses.length > 0) {
                calculate_balance(crypto, used_addresses);
            }
            $("#wallets").show();
            $("#loading_screen").hide();
        }, 10, [], []);

        box.find(".deposit_shift_down, .deposit_shift_up").click(function() {
            var which = $(this).hasClass('deposit_shift_up');
            var qr_container = box.find(".qr");
            qr_container.empty().append("<img src='" + spinner_url + "'>");
            var address = rotate_deposit(crypto, which);
            box.find(".deposit_address").text(address);
            setTimeout(function() {
                qr_container.empty().qrcode({render: 'png', width: 100, height: 100, text: address});
            }, 1);
        });
    });
}

$(function() {
    $("#wallet_settings").click(function(event) {
        event.preventDefault();
        $("#mnemonic_disp").text(raw_mnemonic);
        $("#settings_modal").dialog({
            title: "Wallet Settings",
        });
    });

    $(".history").click(function() {
        var crypto = $(this).parent().data('currency');
        $("#history_modal").dialog({
            title: "History",
        });
    });

    $(".exchange").click(function() {
        var crypto = $(this).parent().data('currency');
        $("#exchange_modal").dialog({
            title: "Exchange",
        });
    });

    $(".send").click(function() {
        var crypto = $(this).parent().data('currency');
        $("#sending_crypto_unit").text(crypto);

        $("#send_modal").dialog({
            title: "Send " + crypto.toUpperCase(),
            buttons: [{
                text: "Send",
                click: function() {
                    var crypto = $("#sending_crypto_unit").text();
                    var sending_address = $("#sending_recipient_address").val();
                    var sending_amount = parseFloat($("#sending_crypto_amount").val());
                    var fee = parseFloat($(""));
                    send_coin(crypto, [sending_address, sending_amount], fee);
                }
            }]
        });

        $.ajax({
            url: "/api/optimal_fee/average3?currency=" + crypto,
        }).success(function(response) {
            //console.log(response);
            var fee_per_byte = parseFloat(response.optimal_fee_per_KiB) / 1024;
            optimal_fees[crypto] = fee_per_byte;

            //console.log('using optmal fee per byte:', fee_per_byte);
            $("#full_fee_rate").text(fee_per_byte.toFixed(2));
            $("#half_fee_rate").text((fee_per_byte / 2).toFixed(2));
            $("#double_fee_rate").text((fee_per_byte * 2).toFixed(2));
        });
    });

    $(".crypto_amount").keyup(function() {
        var crypto = $("#sending_crypto_unit").text();
        var exchange_rate = get_exchange_rate(crypto);
        var converted = exchange_rate * parseFloat($(this).val());
        if(converted) {
            $(".fiat_amount").val(converted.toFixed(2));
        }
    });

    $(".fiat_amount").keyup(function() {
        var crypto = $("#sending_crypto_unit").text();
        var exchange_rate = get_exchange_rate(crypto);
        var converted = (1 / exchange_rate) * parseFloat($(this).val());
        if(converted) {
            $("#sending_crypto_amount").val(converted.toFixed(8));
        }
    });
});
