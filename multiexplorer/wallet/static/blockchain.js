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

function get_unused_change_address(crypto) {
    var i = 0;
    var change_address = undefined;
    while(true) {
        change_address = get_change_keypair(crypto, i)[1];
        if(used_addresses[crypto].indexOf(change_address) == -1) {
            return change_address;
        }
        i += 1;
    }
}

function get_privkey(crypto, address) {
    // Get the private key for address in this wallet. Do not pass in an address
    // that is not part of this wallet because it will loop forever.
    var i = 0;
    while(true) {
        var data = get_change_keypair(crypto, i);
        var privkey = data[0];
        var this_address = data[1];

        if(address == this_address) {
            return privkey;
        }

        data = get_deposit_keypair(crypto, i);
        privkey = data[0];
        this_address = data[1];

        if(address == this_address) {
            return privkey;
        }
        i += 1;
    }
}

function get_privkeys_from_inputs(crypto, inputs) {
    var privkeys = [];
    $.each(inputs, function(i, input) {
        privkeys.push(get_privkey(crypto, input.address))
    });
    return privkeys
}

function estimate_tx_size(in_count, out_count) {
    return out_count * 34 + 148 * in_count + 10
}

function actual_tx_size_estimation(crypto, satoshis_will_send, outs_length) {
    var used_ins = [];
    $.each(utxos[crypto], function(i, utxo) {
        used_ins.push(utxo);
        var added = used_ins.reduce(function(x, y) {return x+y.amount}, 0);
        if(added >= satoshis_will_send) {
            return false;
        }
    });
    //console.log("this tx will have", used_ins.length, "inputs");
    var est = estimate_tx_size(used_ins.length, outs_length)
    //console.log("estimated tx size:", est);
    return est
}

function make_tx(crypto, recipients, optimal_fee_multiplier) {
    // recipients must be list of lists, first item is address, second item is
    // satoshi amount to send to that address.

    var fee_per_kb = optimal_fees[crypto] * optimal_fee_multiplier;
    var tx = new bitcore.Transaction()

    var total_outs = 0;
    $.each(recipients, function(i, recip) {
        var address = recip[0];
        var amount = recip[1];
        //console.log("adding amount", amount);
        tx = tx.to(address, amount);
        total_outs += amount / 1e8;
    });

    var estimated_fee = 0;
    var estimated_size = 0;
    var total_added = 0;
    var inputs_to_add = [];
    $.each(utxos[crypto], function(i, utxo) {
        inputs_to_add.push(utxo);
        total_added += utxo.amount;

        estimated_size = estimate_tx_size(inputs_to_add.length, recipients.length + 1); // +1 for change
        estimated_fee = parseInt(estimated_size / 1024 * fee_per_kb);

        if(total_added >= total_outs + estimated_fee) {
            return false;
        }
    });

    console.log("total inputs amount:", total_added);
    console.log("using fee per kb:", fee_per_kb, "with multiplier of", optimal_fee_multiplier);
    console.log("estimated fee", estimated_fee, "estimated size", estimated_size);
    console.log("adding inputs", inputs_to_add, "Fee per KB:", fee_per_kb);

    tx = tx.from(inputs_to_add);
    tx = tx.change(get_unused_change_address(crypto));
    tx = tx.fee(estimated_fee);
    tx = tx.sign(get_privkeys_from_inputs(crypto, inputs_to_add));
    return tx;
}

function push_tx(crypto, tx, success_callback, fail_callback) {
    $.ajax({
        url: "/api/push_tx/fallback",
        type: "post",
        data: {currency: crypto, tx: tx.toString()}
    }).success(function(response){
        follow_unconfirmed(crypto, response.txid);
        success_callback(response);
    }).fail(function(jqXHR) {
        fail_callback(jqXHR.responseJSON.error);
    });
}

function follow_unconfirmed(crypto, txid, amount) {
    // Takes care of hiding and showing the "unconfirmed" box at the top.

    var box = $(".crypto_box[data-currency=" + crypto + "]");
    var area = box.find(".unconfirmed_area").show();
    area.find(".amount").text(amount.toFixed(8));
    area.find(".txid").text(txid);
    setTimeout(function() {
        $.ajax({
            url: "/api/get_single_transaction?currency=" + crypto + "&txid=" + txid
        }).success(function(){
            if(response.confirmations < 1) {
                var bal = box.find(".crypto_balance");
                var existing = parseFloat(bal.text());
                var new_balance = existing + amount;
                bal.text(new_balance.toFixed(8));
                area.hide();
                return
            } else {
                follow_unconfirmed(crypto, txid, amount);
            }
        });
    }, 60);
}

function get_optimal_fee(crypto, area) {
    $.ajax({
        url: "/api/optimal_fee/average3?currency=" + crypto,
    }).success(function(response) {
        var fee_per_kb = parseFloat(response.optimal_fee_per_KiB);
        optimal_fees[crypto] = fee_per_kb;
        if(area) {
            area.text((fee_per_kb / 1024).toFixed(0));
            fill_in_fee_radios(crypto, 340); // seed with typical tx size of 340 bytes.
        }
    });
}

function get_utxos(crypto, sweep_address, sweep_callback) {
    if(sweep_address) {
        var addrs = "address=" + sweep_address;
    } else {
        addresses = used_addresses[crypto];
        //console.log("getting utxos for", addresses);
        if(addresses.length == 1) {
            var addrs = "address=" + addresses[0];
        } else {
            var addrs = "addresses=" + addresses.join(',');
        }
    }
    $.ajax({
        url: "/api/unspent_outputs/fallback?" + addrs + "&currency=" + crypto,
    }).success(function(response) {
        // sort so highest value utxo is the first element.
        var sorted = response.utxos.sort(function(x,y){return y.amount-x.amount});
        var rewritten = [];
        $.each(sorted, function(i, utxo) {
            // rewrite the utxo list to be in a format that Bitcore can understand.
            rewritten.push({
                script: utxo.scriptPubKey,
                txid: utxo.txid,
                outputIndex: utxo.vout,
                amount: utxo.amount / 1e8,
                address: utxo.address
            })
        });
        if(sweep_address) {
            sweep_callback(rewritten);
        } else {
            utxos[crypto] = rewritten;
        }
    });
}
