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
        if(get_blockchain_data(crypto, 'used_addresses').indexOf(change_address) == -1) {
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
    return privkeys;
}

function estimate_tx_size(in_count, out_count) {
    return out_count * 34 + 148 * in_count + 10
}

function get_blockchain_data(crypto, type) {
    var result = localStorage[type + ':' + crypto];
    if(!result) return
    return JSON.parse(result);
}

function set_blockchain_data(crypto, type, data) {
    localStorage[type + ':' + crypto] = JSON.stringify(data);
}

function remove_duplicates_from_history(crypto) {
    var all_txids = [];
    var rewritten_history = []
    $.each(get_blockchain_data(crypto, 'tx_history'), function(i, tx) {
        if(all_txids.indexOf(tx.txid) != -1) {
            return // duplicate, don't make part of rewritten history...
        }
        rewritten_history.push(tx);
        all_txids.push(tx.txid);
    });
    set_blockchain_data(crypto, 'tx_history', rewritten_history);
}

function concat_blockchain_data(crypto, type, data) {
    localStorage[type + ':' + crypto] = JSON.stringify(get_blockchain_data(crypto, type).concat(data));
    return get_blockchain_data(crypto, type);
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
    var est = estimate_tx_size(used_ins.length, outs_length);
    return est;
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

    if (crypto == 'rdd') {
        tx.version = 2;
    }

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

function push_tx(crypto, tx, success_callback, fail_callback, amount_transacted) {
    console.log("pushing tx:", tx.toString());
    $.ajax({
        url: "/api/push_tx/fallback",
        type: "post",
        data: {currency: crypto, tx: tx.toString()}
    }).success(function(response){
        concat_blockchain_data(crypto, 'used_addresses', [get_unused_change_address(crypto)]);
        follow_unconfirmed(crypto, response.txid, amount_transacted);
        success_callback(response);
    }).fail(function(jqXHR) {
        fail_callback(jqXHR.responseJSON.error);
    });
}

function follow_onchain_exchange(deposit_crypto, deposit_amount, withdraw_crypto, withdraw_amount, deposit_address) {
    var deposit_exchange_area = $(".crypto_box[data-currency=" + deposit_crypto + "] .outgoing_exchange_in_progress");
    var withdraw_exchange_area = $(".crypto_box[data-currency=" + withdraw_crypto + "] .incoming_exchange_in_progress");

    deposit_exchange_area.find(".withdraw_currency").text(withdraw_crypto);
    deposit_exchange_area.find(".withdraw_amount").text(withdraw_amount.toFixed(8));
    deposit_exchange_area.find(".deposit_amount").text(deposit_amount.toFixed(8));

    withdraw_exchange_area.find(".deposit_currency").text(deposit_crypto);
    withdraw_exchange_area.find(".withdraw_amount").text(withdraw_amount.toFixed(8));
    withdraw_exchange_area.find(".deposit_amount").text(deposit_amount.toFixed(8));

    deposit_exchange_area.show();
    withdraw_exchange_area.show();

    setTimeout(function() {
        $.ajax({
            url: "/api/onchain_exchange_status?deposit_currency=" + deposit_crypto + "&address=" + deposit_address,
        }).success(function(response) {
            deposit_exchange_area.find(".error_area").text("");
            var sign = deposit_exchange_area.find(".current_status");
            if(response.status == 'received') {
                sign.css({color: "green"}).text("Received");
                follow_onchain_exchange(
                    deposit_crypto, deposit_amount, withdraw_crypto,
                    withdraw_amount, deposit_address
                );
            } else if(response.status == 'no_deposits') {
                sign.css({color: 'gray'}).text("Unacknowledged");
                follow_onchain_exchange(
                    deposit_crypto, deposit_amount, withdraw_crypto,
                    withdraw_amount, deposit_address
                );
            } else if(response.status == 'complete') {
                var txid = response.transaction;
                deposit_exchange_area.hide();
                withdraw_exchange_area.hide();
                follow_unconfirmed(withdraw_crypto, txid, withdraw_amount);
            }
        }).fail(function(jqXHR, responseText) {
            if(jqXHR.responseJSON) {
                deposit_exchange_area.find(".error_area").text(jqXHR.responseJSON.error);
            } else {
                deposit_exchange_area.find(".error_area").text(responseText);
            }
            follow_onchain_exchange(
                deposit_crypto, deposit_amount, withdraw_crypto,
                withdraw_amount, deposit_address
            );
        });
    }, 10000);
}

function follow_unconfirmed(crypto, txid, amount) {
    // Takes care of hiding and showing the "unconfirmed" box at the top.

    var box = $(".crypto_box[data-currency=" + crypto + "]");
    var area = box.find(".unconfirmed_area").show();
    var local_amount = amount;

    if(amount > 0) {
        area.find(".amount_sign").text("+");
        area.find(".amount_color").css({color: "green"});
        area.css({border: "2px dotted green"});
    } else {
        area.find(".amount_sign").text("");
        area.find(".amount_color").css({color: "red"});
        area.css({border: "2px dotted red"});
    }
    var er = exchange_rates[crypto]['rate']
    area.find(".unconfirmed_fiat").text((amount * er).toFixed(2));

    area.find(".amount").text(amount.toFixed(8));
    area.find(".txid").text(txid);
    setTimeout(function() {
        $.ajax({
            url: "/api/single_transaction/random?currency=" + crypto + "&txid=" + txid
        }).done(function(response) {
            area.find(".error_area").text("");
            var tx = response.transaction;
            var from_response_amount = my_amount_for_tx(crypto, tx);
            if(from_response_amount.toFixed(8) != local_amount.toFixed(8)) {
                console.log("Transaction amount is different than expected:", from_response_amount, local_amount);
            }
            local_amount = from_response_amount;

            if(tx.confirmations >= 1) {
                console.log(crypto, "got a confirmation!");
                var bal = box.find(".crypto_balance");
                var existing = parseFloat(bal.text());
                var new_balance = existing + amount;
                bal.text(new_balance.toFixed(8));
                area.hide();
                box.find(".fiat_balance").css({color: "inherit"}).text((er * new_balance).toFixed(2));
                update_total_fiat_balance();
                concat_blockchain_data(crypto, 'tx_history', [tx]);
                generate_history(crypto);
                return
            } else {
                console.log("still unconfirmed, iterating", local_amount, crypto);
                follow_unconfirmed(crypto, txid, local_amount);
            }
        }).fail(function(jqXHR, textStatus, errorThrown) {
            var error = "Network Error";
            if(jqXHR.responseJSON) {
                error = jqXHR.responseJSON.error;
            }
            area.find(".error_area").text(error);
            follow_unconfirmed(crypto, txid, local_amount);
        });
    }, 30000);
}

function get_optimal_fee(crypto, area) {
    $.ajax({
        url: "/api/optimal_fee/average3?currency=" + crypto,
    }).done(function(response) {
        var fee_per_kb = parseFloat(response.optimal_fee_per_KiB);
        optimal_fees[crypto] = fee_per_kb;
        if(area) {
            area.text((fee_per_kb / 1024).toFixed(0));
            fill_in_fee_radios(crypto, 340); // seed with typical tx size of 340 bytes.
        }
    });
}

function get_sweep_utxos(crypto, sweep_address, sweep_callback) {
    // Given a sweep address, call the UTXOs API endpoint and pass
    // all UTXOS into the callback.

    var addrs = "address=" + sweep_address;

    $.ajax({
        url: "/api/unspent_outputs/fallback?" + addrs + "&currency=" + crypto,
    }).done(function(response) {
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
        sweep_callback(rewritten)
    }).fail(function(jqXHR, textStatus, errorThrown) {
        var error = "Network Error";
        if(jqXHR.responseJSON) {
            error = jqXHR.responseJSON.error;
        }
        var cbox = $(".crypto_box[data-currency=" + crypto + "]");
        cbox.find(".send_ui").hide();
        cbox.find(".utxo_error_area").text(error);
    });
}

function get_utxos2(crypto) {
    var utxos = [];
    var history = get_blockchain_data(crypto, 'tx_history');
    var my_addresses = get_blockchain_data(crypto, 'used_addresses');

    function is_unspent(txid) {
        // look through all history and see if this txid has been included
        // in any inputs. (is unspent)
        var is_spent = false;
        $.each(history, function(i, tx){
            $.each(tx.inputs, function(j, input){
                if(input.txid == txid) {
                    is_spent = true;
                    return false;
                }
            });
            if(is_spent) return false; // stop iteration
        });
        return !is_spent;
    }

    $.each(history, function(i, tx){
        $.each(tx.outputs, function(j, out){
            $.each(my_addresses, function(k, address) {
                if(out.address == address && is_unspent(tx.txid)){
                    // is an incoming payment to one of my addresses
                    utxos.push({
                        address: out.address,
                        amount: out.amount / 1e8,
                        script: out.scriptPubKey,
                        outputIndex: j,
                        txid: tx.txid
                    });
                    return false; //stop iteration
                }
            });
        });
    });
    return utxos
}

function my_amount_for_tx(crypto, tx) {
    var my_addresses = get_blockchain_data(crypto, 'used_addresses');
    var my_amount = 0;
    $.each(tx.inputs, function(i, input) {
        if(my_addresses.indexOf(input.address) != -1) {
            //console.log("subtracting input of", input.address, input.amount / 1e8);
            my_amount -= input.amount / 1e8;
        }
    });
    $.each(tx.outputs, function(i, output) {
        if(my_addresses.indexOf(output.address) != -1) {
            //console.log("adding output of", output.address, output.amount / 1e8);
            my_amount += output.amount / 1e8;
        }
    });
    //console.log("found:", my_amount, "from tx:", tx);
    return my_amount
}
