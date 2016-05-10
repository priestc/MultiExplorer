var text_spinner = '<div class="thin-spinner spinner" style="height: 10px; width: 10px;"></div>';
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

function get_crypto_balance(crypto) {
    return parseFloat(
        $(".crypto_box[data-currency=" + crypto.toLowerCase() + "]").find('.crypto_balance').text()
    )
}

function validate_address(crypto, address) {
    if(crypto == 'btc') {
        crypto = 'livenet'
    }
    if(bitcore.Address.isValid(address, bitcore.Networks.get(crypto))) {
        return true
    }
    return false
}

function add_to_balance(crypto, addresses) {
    // active_deposit_addresses == list of dposit addresses that have acivity
    // these addresses will make up the balance. (plus the change addresses
    // which will be made in another concurrent thread)

    //console.log("calculate balances with:", addresses);

    var box = $(".crypto_box[data-currency=" + crypto + "]");
    box.find(".fiat_balance").html(text_spinner);

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
        bal.text(new_balance.toFixed(8));

        var exchange_rate = exchange_rates[crypto]['rate'];
        //console.log("using fiat exchange rate", exchange_rate, (exchange_rate * new_balance).toFixed(2));
        box.find(".fiat_balance").css({color: "inherit"}).text((exchange_rate * new_balance).toFixed(2));
    }).fail(function() {
        box.find(".fiat_balance").css({color: "red"}).text("Error getting balance.");
        box.find(".switch_to_send").hide(); //attr('disabled', 'disabled');
    });
}

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
        box.find(".fiat_balance").css({color: 'red'}).text("Network error getting balance.");
        box.find(".deposit_address").css({color: 'red'}).text(jqXHR.responseJSON.error);
        box.find(".switch_to_send").hide(); //attr('disabled', 'disabled');
        box.find(".switch_to_exchange").hide(); //attr('disabled', 'disabled');
        box.find(".switch_to_history").hide(); //attr('disabled', 'disabled');
    })
}

function rotate_deposit(crypto, up) {
    var pool = unused_deposit_addresses[crypto];
    unused_deposit_addresses[crypto] = arrayRotate(pool, up);
    return pool[0];
}

function open_wallet(show_wallet_list) {
    $("#wallet_settings_wrapper").show();
    $.each(crypto_data, function(i, data) {
        var crypto = data.code;
        var box = $(".crypto_box[data-currency=" + crypto + "]");

        if(show_wallet_list.indexOf(crypto) == -1) {
            box.hide();
            return; // don't do anything if this crypto is disabled.
        } else {
            if(box.css('display') != 'none') {
                return; // don't do anything if it's enabled and already open
            }
        }

        box.show();

        used_addresses[crypto] = [];

        fetch_used_addresses(crypto, 'deposit', function(found_used_addresses) {
            //console.log(crypto, "======== found deposit addresses:", found_used_addresses);
            used_addresses[crypto] = used_addresses[crypto].concat(found_used_addresses);

            var address = unused_deposit_addresses[crypto][0];
            box.find(".deposit_address").text(address);
            box.find(".qr").empty().qrcode({render: 'div', width: 100, height: 100, text: address});

            if(found_used_addresses.length == 0) {
                // if the external chain has no activity, then the internal chain
                // must have none either. Don't bother calculating balance.
                box.find(".crypto_balance").text("0.0");
                box.find(".fiat_balance").text("0.0");
                box.find(".switch_to_send").hide();
                box.find(".switch_to_exchange").hide();
                box.find(".switch_to_history").hide();
            } else {
                add_to_balance(crypto, found_used_addresses);
                box.find(".switch_to_send").show();
                box.find(".switch_to_exchange").show();
                box.find(".switch_to_history").show();
            }
        }, 10, [], []);

        fetch_used_addresses(crypto, 'change', function(found_used_addresses) {
            //console.log(crypto, "======== found change addresses", found_used_addresses);
            used_addresses[crypto] = used_addresses[crypto].concat(found_used_addresses);

            if(found_used_addresses.length > 0) {
                add_to_balance(crypto, found_used_addresses);
            }
            box.show();
            $("#loading_screen").hide();
        }, 10, [], []);

        box.find(".deposit_shift_down, .deposit_shift_up").click(function() {
            var which = $(this).hasClass('deposit_shift_up');
            var qr_container = box.find(".qr");
            qr_container.empty().append(text_spinner);
            var address = rotate_deposit(crypto, which);
            box.find(".deposit_address").text(address);
            setTimeout(function() {
                qr_container.empty().qrcode({render: 'png', width: 100, height: 100, text: address});
            }, 1);
        });
    });
}

function refresh_fiat() {
    // after new fiat exchanage rates come in, this function gets called which
    // recalculates balances from new rates.
    $(".crypto_box:visible").each(function(i, dom_box){
        var box = $(dom_box);
        var crypto = box.data('currency');
        var crypto_balance = parseFloat(box.find('.crypto_balance').text());
        var new_fiat = crypto_balance * exchange_rates[crypto]['rate'];
        box.find('.fiat_balance').text(new_fiat.toFixed(2));
    });
}

function fill_in_settings(settings) {
    // this function gets called every time the settings are changed, and
    // also once when the app first loads.

    var form = $("#settings_form");

    form.find("select[name=display_fiat]").val(settings.display_fiat_unit);
    $(".fiat_unit").text(settings.display_fiat_unit.toUpperCase());
    $(".fiat_symbol").text(settings.display_fiat_symbol);

    form.find("select[name=auto_logout]").val(settings.auto_logout);

    $.each(settings.show_wallet_list, function(i, crypto) {
        form.find("input[value=" + crypto + "]").attr("checked", "checked");
        show_wallet_list.push(crypto);
    });
    open_wallet(settings.show_wallet_list);
}

function update_actual_fee_estimation(crypto, satoshis_will_send, outs_length) {
    var used_ins = [];
    $.each(utxos[crypto], function(i, utxo) {
        used_ins.push(utxo);
        var added = used_ins.reduce(function(x, y) {return x+y.amount}, 0);
        if(added >= satoshis_will_send) {
            return false;
        }
    });
    var tx_size = estimate_tx_size(used_ins.length, outs_length)
    fill_in_fee_radios(crypto, tx_size);
}

function fill_in_fee_radios(crypto, tx_size) {
    /// Based on exchange rates and optimal fee estimations, guess how much
    // the fees would be in fiat for a given tx size. This function fills in the
    // estimations onto the page.

    var fee_per_kb = optimal_fees[crypto];
    var fiat_exchange = exchange_rates[crypto]['rate'];
    var fiat_fee_this_tx = (fee_per_kb / 1024) * tx_size * fiat_exchange / 1e8;
    var box = $(".crypto_box[data-currency=" + crypto + "]");

    box.find(".full_fee_rate").text(fiat_fee_this_tx.toFixed(2));
    box.find(".half_fee_rate").text((fiat_fee_this_tx / 2).toFixed(2));
    box.find(".double_fee_rate").text((fiat_fee_this_tx * 2).toFixed(2));
}

function switch_section(crypto, to_section) {
    box.find(".send_part").hide();
    box.find(".receive_part").hide();
    box.find(".exchange_part").hide();
    box.find(".history_part").hide();
    box.find(".sweep_part").hide();

    box.find("." + to_section + "_part").show();
}

$(function() {
    $("#wallet_settings").click(function(event) {
        event.preventDefault();
        $("#mnemonic_disp").text(raw_mnemonic);
        $("#settings_modal").dialog({
            title: "Wallet Settings",
            buttons: [{
                text: "Save Settings",
                click: function() {
                    var form = $("#settings_form");
                    var swl = [];
                    form.find(".supported_crypto:checked").each(function(i, crypto) {
                        var c = $(crypto);
                        swl.push(c.val())
                    });
                    var settings = {
                        auto_logout: form.find("select[name=auto_logout]").val(),
                        display_fiat: form.find("select[name=display_fiat]").val(),
                        show_wallet_list: swl.join(','),
                    }
                    $.ajax({
                        url: '/wallet/save_settings',
                        type: 'post',
                        data: settings,
                    }).success(function(response) {
                        settings.show_wallet_list = swl; // replace comma seperated string with list
                        fill_in_settings(response.settings);
                        if(response.exchange_rates) {
                            exchange_rates = response.exchange_rates;
                            refresh_fiat();
                        }
                        $("#settings_modal").dialog('close');
                    });
                }
            }]
        });
    });

    $(".cancel_button").click(function() {
        var box = $(this).parent().parent();
        switch_section("receive");
    });

    $(".switch_to_history").click(function() {
        var box = $(this).parent().parent();
        var crypto = box.data('currency');

        switch_section("history");
    });

    $(".switch_to_sweep").click(function() {
        var box = $(this).parent().parent();
        var error_area = box.find(".sweep_part .error_area")
        var crypto = box.data('currency');

        switch_section("sweep");

        get_optimal_fee(crypto, box);

        box.find(".submit_sweep").unbind('click').click(function() {
            box.find(".sweep_part .error_area").html(text_spinner);
            var priv = box.find(".sweeping_key").val();
            var fee_multiplier = parseFloat(box.find(".sweep_part .fee_selector:checked").val());
            var fee_per_kb = optimal_fees[crypto] * fee_multiplier;

            //console.log("Sweeping with fee multiplier of", fee_multiplier);
            //console.log("fee per kb", fee_per_kb);

            var network = crypto;
            if(crypto == 'btc') {
                network = 'livenet';
            }
            var net = bitcore.Networks.get(network);
            var sweep_priv = new bitcore.PrivateKey(priv);
            var sweep_address = sweep_priv.toAddress(net);

            get_utxos(crypto, sweep_address, function(utxos) {
                var tx = new bitcore.Transaction()
                var amount = 0;
                var input_count = 0;
                var to_address = get_unused_change_address(crypto);
                $.each(utxos, function(i, utxo) {
                    amount += utxo.amount;
                    input_count += 1
                    if(input_count >= 670) {
                        console.log("reached limit of 100KB, stopping at 670 inputs");
                        return false;
                    }
                });
                if(amount == 0) {
                    error_area.html("Private Key does not have a balance.");
                    return
                }
                var estimated_size = estimate_tx_size(utxos.length, 1);
                var estimated_fee = parseInt(estimated_size / 1024 * fee_per_kb);
                var minus_fee = (amount * 1e8) - estimated_fee;

                //console.log("estimated fee", estimated_fee, "estimated size", estimated_size);
                //console.log("adding inputs", utxos, "Fee per KB:", fee_per_kb);
                //console.log("sending", minus_fee);

                tx = tx.from(utxos);
                tx = tx.to(get_unused_change_address(crypto), minus_fee);
                tx = tx.fee(estimated_fee);
                tx = tx.sign(sweep_priv);

                //console.log(tx.toString());

                push_tx(crypto, tx, function(response) {
                    error_area.css({color: 'inherit'}).html("Sweep Completed!");
                }, function(error_msg) {
                    error_area.css({color: 'red'}).text(error_msg);
                });
            });
        });
    });

    $(".sweeping_key").keyup(function(event) {
        // Validate the private key as the user types. Once a valid private
        // key has been entered, make the sweep button enabled.
        var box = $(this).parent().parent().parent();
        var priv = $(this).val();
        var crypto = box.data('currency');

        if(crypto == 'btc') {
            crypto = 'livenet';
        }
        var valid = bitcore.PrivateKey.isValid(priv, bitcore.Networks.get(crypto));
        var error_area = box.find(".sweep_part .error_area");
        if(valid) {
            error_area.css({color: 'inherit'}).text("");
            $(this).css({color: 'inherit'});
            box.find(".submit_sweep").removeAttr('disabled');
        } else {
            error_area.css({color: 'red'}).text("Invalid Private Key");
            $(this).css({color: 'red'});
            box.find(".submit_sweep").attr('disabled', 'disabled');
        }
    });

    $(".switch_to_exchange").click(function() {
        var box = $(this).parent().parent();
        var crypto = box.data('currency');

        switch_section("exchange");

        $.ajax({
            type: 'get',
            url: '/onchain_exchange_rates?deposit_currency=' + crypto,
        }).succes(function(response) {
            $.each(response.pairs, function() {
                var to_code = pair.withdraw_currency.code;
                var to_name = pair.withdraw_currency.name + " (" + to_code + ")";
                if(show_wallet_list.indexOf(to_code) != -1) {
                    var img_url = $(".crypto_box[data-currency=" + to_code + "] img").attr('src');
                    var icon = "<img src='" + img_url + "' style='width: 30px; height: 30px'>";
                    var table = "<table><tr><td>" + icon + "</td><td>" + to_name + "</td></tr></table>";
                    box.find(".exchange_options").append(table);
                }
            });
        });
    });

    $(".switch_to_send").click(function() {
        var box = $(this).parent().parent();
        var crypto = box.data('currency');

        switch_section("send");

        get_utxos(crypto);
        get_optimal_fee(crypto, box);

        box.find(".submit_send").unbind('click').click(function() {
            var sending_address = box.find(".sending_recipient_address").val();
            var sending_amount = parseFloat(box.find(".sending_crypto_amount").val());
            var fee_multiplier = parseFloat(box.find(".send_part .fee_selector:checked").val());
            var fee_per_kb = optimal_fees[crypto] * fee_multiplier;
            var tx = send_coin(crypto, [[sending_address, sending_amount * 1e8]], fee_per_kb);

            push_tx(crypto, tx, function(response) {
                console.log("push tx successful!", response);
            }, function(error_msg) {
                box.find(".send_part .error_area").text(error_msg);
            });
        });
    });

    // The below two functions get called whenever the user changes the fiat,
    // crypto amount, or address field in the sending section.

    $(".sending_recipient_address").keyup(function(event) {
        var sending_address = $(this).val();
        var box = $(this).parent().parent().parent();
        var crypto = box.data('currency');

        if(!validate_address(crypto, sending_address)) {
            box.find(".submit_send").attr('disabled', 'disabled');
            box.find(".send_part .error_area").text("Invalid Sending Address");
            $(this).css({color: 'red'});
        } else {
            box.find(".submit_send").removeAttr('disabled');
            box.find(".send_part .error_area").text("");
            $(this).css({color: 'inherit'});
        }
    });

    $(".sending_fiat_amount, .sending_crypto_amount").keyup(function(event) {
        if(event.keyCode == 9) {
            return // tab key was pressed
        }
        var box = $(this).parent().parent().parent();
        var which = "fiat";
        if($(this).hasClass("sending_crypto_amount")) {
            which = "crypto";
        }
        var crypto = box.data('currency');
        var value_entered = parseFloat($(this).val());

        var er = exchange_rates[crypto]['rate'];

        var converted = er * value_entered;
        if(which == 'fiat') {
            converted = (1 / er) * value_entered;
        }

        if(converted) {
            if(which == 'fiat') {
                box.find(".sending_crypto_amount").val(converted.toFixed(8));
            } else {
                box.find(".sending_fiat_amount").val(converted.toFixed(2));
            }
        } else {
            return
        }

        var to_compare = value_entered;
        var sat = (value_entered * 1e8).toFixed(0);

        if(which == 'fiat') {
            to_compare = converted;
            sat = (converted * 1e8).toFixed(0)
        }

        var crypto_balance = get_crypto_balance(crypto);

        if(to_compare > crypto_balance) {
            box.find(".sending_fiat_amount, .sending_crypto_amount").css({color: 'red'});
            box.find(".submit_send").attr('disabled', 'disabled');
            box.find(".send_part .error_area").text("Amount exceeds balance");
        } else {
            box.find(".sending_fiat_amount, .sending_crypto_amount").css({color: 'inherit'});
            box.find(".submit_send").removeAttr('disabled');
            box.find(".send_part .error_area").text("");
        }
        update_actual_fee_estimation(crypto, sat, 1);
    });

    $(".fee_selector").change(function() {
        var container = $(this).parents(".fee_wrapper");
        var all_containers = container.parents(".subsection");
        all_containers.find(".fee_wrapper").removeClass('selected');
        container.addClass("selected");
    });
});
