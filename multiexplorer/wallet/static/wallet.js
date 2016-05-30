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

function update_balance(crypto) {
    var box = $(".crypto_box[data-currency=" + crypto + "]");
    var bal = box.find(".crypto_balance");
    var calculated_balance = generate_history(crypto);
    bal.text(calculated_balance.toFixed(8));

    var exchange_rate = exchange_rates[crypto]['rate'];
    box.find(".fiat_balance").css({color: "inherit"}).text((exchange_rate * calculated_balance).toFixed(2));
    update_total_fiat_balance();
}

function update_outstanding_ajax(crypto, value) {
    // this keeps track of how many ajax calls are outstanding for each crypto.
    // it is needed because there are always two simoutaneously occuring chains
    // of addresses to check for activity. When both deposit and change chains are finished,
    // the spinner will stop. `value` should be either +1 or -1.

    var box = $(".crypto_box[data-currency=" + crypto + "]");
    var count = box.find(".outstanding_ajax_counter");
    var existing = parseInt(count.text());
    var new_ = existing + value;
    count.text(new_);

    if(new_ == 0) {
        box.find(".spinner").first().hide();
    } else {
        box.find(".spinner").first().show();
    }
    return new_
}

function fetch_used_addresses(crypto, chain, blank_length, already_tried_addresses, all_used_arg) {
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

    var addresses_with_activity = [];
    if(addresses.length == 1) {
        var args = "?address=" + addresses[0];
        var mode = "fallback";
    } else {
        var args = "?addresses=" + addresses.join(",");
        var mode = "private5";
    }

    args += "&extended_fetch=true&currency=" + crypto;

    var all_my_addresses = already_tried_addresses.concat(addresses);

    var box = $(".crypto_box[data-currency=" + crypto + "]");

    update_outstanding_ajax(crypto, 1);
    $.ajax({
        'url': "/api/historical_transactions/" + mode + "/" + args,
        'type': 'get',
    }).done(function (response) {
        var txs = response['transactions'];
        tx_history[crypto] = tx_history[crypto].concat(txs);
        $.each(txs, function(i, tx) {
            var ins_and_outs = tx.inputs.concat(tx.outputs);
            $.each(ins_and_outs, function(i, in_or_out) {
                var address = in_or_out['address'];
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

        var all_tried = addresses.concat(already_tried_addresses);
        all_used = addresses_with_activity.concat(all_used);

        var needs_to_go = addresses_with_activity.length;

        if(needs_to_go == 0) {
            // all results for this iteration returned no activity
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
            used_addresses[crypto] = used_addresses[crypto].concat(all_used);
            return // stop iteration
        } else {
            fetch_used_addresses(crypto, chain, needs_to_go, all_tried, all_used);
        }
    }).fail(function(jqXHR, textStatus, errorThrown) {
        var error = "Network Error";
        if(jqXHR.responseJSON) {
            error = jqXHR.responseJSON.error
        }

        box.find(".internal_error").text(error);
        box.find(".switch_to_send").hide();
        box.find(".switch_to_exchange").hide();
        box.find(".switch_to_history").hide();
        box.find(".receive_part").hide();
        box.find(".qr").empty();

    }).always(function() {
        var outstanding = update_outstanding_ajax(crypto, -1);
        if (outstanding == 0 && !box.find(".internal_error").text()) {
            $("#loading_screen").hide();
            update_balance(crypto);
            console.log(crypto, "finished getting history for both chains");

            var address = unused_deposit_addresses[crypto][0];
            box.find(".receive_part").show();
            box.find(".deposit_address").text(address);
            box.find(".qr").empty().qrcode({render: 'div', width: 100, height: 100, text: address});

            if(used_addresses[crypto].length == 0) {
                box.find(".crypto_balance").text("0.0");
                box.find(".fiat_balance").text("0.0");
                box.find(".switch_to_send").hide();
                box.find(".switch_to_exchange").hide();
                box.find(".switch_to_history").hide();
            } else {
                box.find(".switch_to_send").show();
                box.find(".switch_to_exchange").show();
                box.find(".switch_to_history").show();
            }

            $.each(tx_history[crypto], function(i, tx) {
                if (tx.confirmations == 0) {
                    console.log("unconfirmed found in history!");
                    var amount = my_amount_for_tx(crypto, tx);
                    follow_unconfirmed(crypto, tx.txid, amount);
                }
            });
        }
    })
}

function rotate_deposit(crypto, up) {
    var pool = unused_deposit_addresses[crypto];
    unused_deposit_addresses[crypto] = arrayRotate(pool, up);
    return pool[0];
}

function load_crypto(crypto) {
    used_addresses[crypto] = [];
    tx_history[crypto] = [];

    var box = $(".crypto_box[data-currency=" + crypto + "]");
    box.find(".crypto_balance").text("0.0");
    box.find(".fiat_balance").text("0.0");

    fetch_used_addresses(crypto, 'deposit', 10, [], []);
    fetch_used_addresses(crypto, 'change', 10, [], []);
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

        load_crypto(crypto);

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
    // recalculates balances from new rates. Also regenerates the history sections
    // to show balances in new currency.
    $(".crypto_box:visible").each(function(i, dom_box){
        var box = $(dom_box);
        var crypto = box.data('currency');
        var crypto_balance = parseFloat(box.find('.crypto_balance').text());
        var new_fiat = crypto_balance * exchange_rates[crypto]['rate'];
        box.find('.fiat_balance').text(new_fiat.toFixed(2));
        generate_history(crypto);
    });
    update_total_fiat_balance();
}

function fill_in_fee_radios(crypto, tx_size) {
    // Based on exchange rates and optimal fee estimations, guess how much
    // the fees would be in fiat for a given tx size. This function fills in the
    // estimations onto the page.

    var fee_per_kb = optimal_fees[crypto];
    var fiat_exchange = exchange_rates[crypto]['rate'];
    var satoshi_fee_this_tx = parseInt((fee_per_kb / 1024) * tx_size);
    var fiat_fee_this_tx = satoshi_fee_this_tx * fiat_exchange / 1e8;

    var box = $(".crypto_box[data-currency=" + crypto + "]");

    box.find(".full_fee_rate").text(fiat_fee_this_tx.toFixed(2));
    box.find(".optimal_fee").text((satoshi_fee_this_tx / 1e8).toFixed(8));
    box.find(".half_fee_rate").text((fiat_fee_this_tx / 2).toFixed(2));
    box.find(".double_fee_rate").text((fiat_fee_this_tx * 2).toFixed(2));

    return satoshi_fee_this_tx;
}

function generate_history(crypto) {
    var history = tx_history[crypto].sort(function(a, b){
        return new Date(b.time) - new Date(a.time);
    });

    var fiat_symbol = $(".fiat_symbol").first().text();
    var fiat_unit = $(".fiat_unit").first().text();

    var history_section = $(".crypto_box[data-currency=" + crypto + "] .history_section");
    history_section.empty();

    var running_total = 0;
    var er = exchange_rates[crypto]['rate'];
    var all_txids = [];
    $.each(history, function(i, tx) {
        if(all_txids.indexOf(tx.txid) != -1) {
            return // duplicate, don't make part of history...
        }

        var my_amount = my_amount_for_tx(crypto, tx);
        if(tx.confirmations >= 1) {
            running_total += my_amount;
        } else {
            console.log("not counting", tx);
            return // don't print 0 confirm to history section.
        }

        var disp = Math.abs(my_amount).toFixed(8)
        //console.log(tx.time, my_amount.toFixed(8));
        if (my_amount > 0) {
            var color_and_sign = "green'>+";
        } else {
            var color_and_sign = "red'>-";
        }

        var fiat = " (" + fiat_symbol + (disp * er).toFixed(2) + " " + fiat_unit + ")";
        var formatted_amount = " <span style='color: " + color_and_sign + disp + " " + crypto.toUpperCase() + fiat + "</span>";

        var time = moment(tx.time).fromNow();

        var explorer_link = "<a target='_blank'  href='/tx/" + crypto + "/" + tx.txid + "'>" + tx.txid.substr(0, 8) + "...</a>";
        history_section.append(explorer_link + " " + time + "<br>" + formatted_amount + "<hr>");
        all_txids.push(tx.txid);
    });

    return running_total;
}

function switch_section(box, to_section) {
    box.find(".send_part").hide();
    box.find(".receive_part").hide();
    box.find(".exchange_part").hide();
    box.find(".history_part").hide();
    box.find(".sweep_part").hide();

    box.find("." + to_section + "_part").show();
}

function update_total_fiat_balance() {
    var bal = 0;
    $(".fiat_balance").each(function(i, ele) {
        var this_bal = parseFloat($(ele).text());
        if(this_bal) bal += this_bal;
    });
    $("#total_fiat_balance_container").show();
    $("#total_fiat_balance").text(bal.toFixed(2));
}

$(function() {
    $(".cancel_button").click(function() {
        var box = $(this).parent().parent();
        switch_section(box, "receive");
    });

    $(".switch_to_history").click(function() {
        var box = $(this).parent().parent();
        var crypto = box.data('currency');

        switch_section(box, "history");
    });

    $(".switch_to_sweep").click(function() {
        var box = $(this).parent().parent();
        var error_area = box.find(".sweep_part .error_area");
        var crypto = box.data('currency');
        var spinner_classes = box.find(".spinner").first().attr('class');

        switch_section(box, "sweep");

        get_optimal_fee(crypto, box.find(".optimal_fee_rate_per_byte"));

        box.find(".submit_sweep").unbind('click').click(function() {
            box.find(".sweep_part .error_area").html(spinner);
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

                tx = tx.from(utxos);
                tx = tx.to(get_unused_change_address(crypto), minus_fee);
                tx = tx.fee(estimated_fee);
                tx = tx.sign(sweep_priv);

                push_tx(crypto, tx, function(response) {
                    error_area.css({color: 'inherit'}).html("Sweep Completed!");
                    switch_section(box, 'receive');
                }, function(error_msg) {
                    error_area.css({color: 'red'}).text(error_msg);
                }, minus_fee / 1e8);
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
        var spinner_classes = box.find(".spinner").first().attr('class');
        var spinner = "<div class='" + spinner_classes + "' style='width: 12px; height: 12px'></div>";

        var crypto = box.data('currency');
        var error_area = box.find(".exchange_part .error_area");
        exchange_pairs[crypto] = [];

        get_utxos(crypto);
        if(!optimal_fees[crypto]) {
            get_optimal_fee(crypto);
        }

        switch_section(box, "exchange");

        var area = box.find(".exchange_options");
        area.append(spinner + " Fetcing supported exchange pairs...");

        $.ajax({
            type: 'get',
            url: '/api/onchain_exchange_rates?deposit_currency=' + crypto,
        }).done(function(response) {
            area.empty();
            $.each(response.pairs, function(i, pair) {
                var to_code = pair.withdraw_currency.code.toLowerCase();
                var to_name = pair.withdraw_currency.name + " (" + to_code.toUpperCase() + ")";
                if(show_wallet_list.indexOf(to_code) != -1) {
                    var unique = crypto + "_exchange";
                    var img_url = $(".crypto_box[data-currency=" + to_code + "] .main_currency_logo").attr('src');
                    var icon = "<img src='" + img_url + "' style='width: 30px; height: 30px'>";
                    var css = "colors-" + to_code + " cancel-colors";
                    var radio = "<input type='radio' name='" + unique + "' value='" + to_code + "' class='exchange_radio'>";
                    var table = "<table class='" + css + "'><tr><td>" + radio + "</td><td>" + icon + "</td><td>" + to_name + "</td></tr></table>";
                    var label = "<label>" + table + "</label>";
                    area.append(label);
                    exchange_pairs[crypto].push(pair);
                }
            });
            box.find(".exchange_radio").first().click();
        });

        box.on('change', ".exchange_radio", function() {
            var selected_code = box.find(".exchange_radio:checked").val().toLowerCase();
            $.each(exchange_pairs[crypto], function(i, pair) {
                if(pair.withdraw_currency.code.toLowerCase() == selected_code) {
                    box.find(".withdraw_unit").text(pair.withdraw_currency.name);
                    box.find(".withdraw_code").text(pair.withdraw_currency.code);
                    box.find(".crypto_to_crypto_rate").text(pair.rate);
                    box.find(".withdraw_fee").text(pair.withdraw_fee);
                    box.find(".deposit.exchange_amount").val('');
                    box.find(".withdraw.exchange_amount").val('');
                    box.find(".max_exchange").text(pair.max_amount);
                    box.find(".min_exchange").text(pair.min_amount);
                    box.find(".fiat.exchange_amount").keyup();
                }
            });
            var container = $(this).parents("table");
            var all_containers = container.parents(".subsection");
            all_containers.find("table").addClass('cancel-colors');
            container.removeClass("cancel-colors");
        });

        box.find(".exchange_amount").unbind('keyup').keyup(function(event) {
            if(event.keyCode < 0x20 && event.keyCode != 8 && event.keyCode != 46) {
                return // non printable char pressed (let backspace & del through)
            }

            var rate = parseFloat(box.find(".crypto_to_crypto_rate").text());
            var withdraw_fee = parseFloat(box.find(".withdraw_fee").text());
            var max = parseFloat(box.find(".max_exchange").text());
            var min = parseFloat(box.find(".min_exchange").text());

            if($(this).hasClass("fiat")) {
                var fiat = parseFloat($(this).val());
                if(!fiat) {
                    deposit = "";
                    withdrawl = "";
                    fiat = "";
                } else {
                    var deposit = fiat / exchange_rates[crypto]['rate'];
                    var withdraw = ((deposit * rate) - withdraw_fee).toFixed(8);

                    var tx_size = actual_tx_size_estimation(crypto, deposit, 2);
                    var deposit_fee_satoshi = fill_in_fee_radios(crypto, tx_size);
                    deposit = (deposit + (deposit_fee_satoshi / 1e8)).toFixed(8);
                }
                box.find(".withdraw.exchange_amount").val(withdraw);
                box.find(".deposit.exchange_amount").val(deposit);
            } else if($(this).hasClass("withdraw")) {
                var withdraw = parseFloat($(this).val()) + withdraw_fee;
                if(!withdraw) {
                    deposit = "";
                    withdrawl = "";
                    fiat = "";
                } else {
                    var deposit = withdraw / rate;
                    var fiat = (deposit * exchange_rates[crypto]['rate']).toFixed(2);

                    var tx_size = actual_tx_size_estimation(crypto, deposit, 2);
                    var deposit_fee_satoshi = fill_in_fee_radios(crypto, tx_size);
                    deposit = (deposit + (deposit_fee_satoshi / 1e8)).toFixed(8);
                }
                box.find(".fiat.exchange_amount").val(fiat);
                box.find(".deposit.exchange_amount").val(deposit);
            } else if($(this).hasClass("deposit")) {
                var deposit = parseFloat($(this).val());
                if(!deposit) {
                    deposit = "";
                    withdrawl = "";
                    fiat = "";
                } else {
                    var tx_size = actual_tx_size_estimation(crypto, deposit, 2);
                    var deposit_fee_satoshi = fill_in_fee_radios(crypto, tx_size);
                    deposit -= (deposit_fee_satoshi / 1e8);

                    var withdraw = ((deposit * rate) - withdraw_fee).toFixed(8);
                    var fiat = (deposit * exchange_rates[crypto]['rate']).toFixed(2);
                }

                box.find(".withdraw.exchange_amount").val(withdraw);
                box.find(".fiat.exchange_amount").val(fiat);
            }

            var balance = parseFloat(box.find('.crypto_balance').text());

            if(deposit == 0) {
                box.find(".submit_exchange").attr('disabled', 'disabled');
                return
            }

            if(deposit && deposit > balance) {
                box.find(".exchange_amount").css({color: 'red'});
                box.find(".submit_exchange").attr('disabled', 'disabled');
                error_area.css({color: 'red'}).text("Wallet balance is not enough")
            } else if (deposit && deposit > max) {
                box.find(".exchange_amount").css({color: 'red'});
                box.find(".submit_exchange").attr('disabled', 'disabled');
                error_area.css({color: 'red'}).text("Deposit larger than maximum");
            } else if(deposit && deposit < min) {
                console.log("Deposit" + deposit + " lower than minimum of " + min);
                box.find(".exchange_amount").css({color: 'red'});
                box.find(".submit_exchange").attr('disabled', 'disabled');
                error_area.css({color: 'red'}).text("Deposit lower than minimum");
            } else {
                box.find(".exchange_amount").css({color: 'inherit'});
                box.find(".submit_exchange").removeAttr('disabled');
                error_area.css({color: 'inherit'}).text('');
            }
        });

        box.find(".submit_exchange").unbind('click').click(function() {
            var deposit_amount = parseFloat(box.find(".deposit.exchange_amount").val());
            var deposit_satoshi = parseInt(deposit_amount * 1e8);
            var withdraw_code = box.find(".withdraw_code").first().text().toLowerCase();
            var optimal_fee_per_kb = parseFloat(box.find(".optimal_fee_per_kb").text());
            var withdraw_amount = parseFloat(box.find(".withdraw.exchange_amount").val());
            var withdraw_address = unused_deposit_addresses[withdraw_code][0];

            error_area.html(spinner + " Calling Exchange...");

            $.ajax({
                url: "https://cors.shapeshift.io/shift",
                type: 'post',
                data: {
                    withdrawal: withdraw_address,
                    pair: (crypto + "_" + withdraw_code).toLowerCase()
                }
            }).done(function(response) {
                var deposit_address = response.deposit;
                var tx = make_tx(crypto, [[deposit_address, deposit_satoshi]], 1.0);
                used_addresses[withdraw_code].push(withdraw_address);
                console.log(tx.toString());
                error_area.html(spinner + " Pushing Transaction...");
                push_tx(crypto, tx, function(response) {
                    error_area.css({color: 'inherit'}).html("Exchange Completed!");
                    console.log("about to call exchange follower:", crypto, deposit_amount, withdraw_code, withdraw_amount, deposit_address);
                    follow_onchain_exchange(crypto, deposit_amount, withdraw_code, withdraw_amount, deposit_address)
                    switch_section(box, 'receive');
                }, function(error_msg) {
                    error_area.css({color: 'red'}).text(error_msg);
                }, deposit_amount * -1); // negative because of send.
            });
        });
    });

    $(".switch_to_send").click(function() {
        var box = $(this).parent().parent();
        var spinner_classes = box.find(".spinner").first().attr('class');
        var spinner = "<div class='" + spinner_classes + "'></div>";

        var crypto = box.data('currency');

        box.find(".fee_wrapper .spinner").attr('class', spinner_classes);

        switch_section(box, "send");

        get_utxos(crypto);
        get_optimal_fee(crypto, box.find(".optimal_fee_rate_per_byte"));

        box.find(".submit_send").unbind('click').click(function() {
            var sending_address = box.find(".sending_recipient_address").val();
            var sending_amount = parseFloat(box.find(".sending_crypto_amount").val());
            var fee_multiplier = parseFloat(box.find(".send_part .fee_selector:checked").val());
            var tx = make_tx(crypto, [[sending_address, sending_amount * 1e8]], fee_multiplier);

            push_tx(crypto, tx, function(response) {
                switch_section(box, 'receive');
            }, function(error_msg) {
                box.find(".send_part .error_area").text(error_msg);
            }, sending_amount * -1);
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
        if(event.keyCode < 0x20 && event.keyCode != 8 && event.keyCode != 46) {
            return // non printable char pressed (tab, shift, del, etc)
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
        var tx_size = actual_tx_size_estimation(crypto, sat, 1);
        fill_in_fee_radios(crypto, tx_size);
    });

    $(".fee_selector").change(function() {
        var container = $(this).parents(".fee_wrapper");
        var all_containers = container.parents(".subsection");
        all_containers.find(".fee_wrapper").removeClass('selected');
        container.addClass("selected");
    });
});
