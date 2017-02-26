var text_spinner = '<div class="thin-spinner spinner" style="height: 10px; width: 10px;"></div>';

function get_crypto_balance(crypto) {
    return parseFloat(
        $(".crypto_box[data-currency=" + crypto.toLowerCase() + "]").find('.crypto_balance').text()
    )
}

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
    if(!exchange_rate) {
        box.find(".fiat_balance").text("0.00");
        box.find(".internal_error").show().text(exchange_rates[crypto]['error']);
    } else {
        box.find(".fiat_balance").css({color: "inherit"}).text((exchange_rate * calculated_balance).toFixed(2));
    }
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

function fetch_history_single_address(crypto, address) {
    update_outstanding_ajax(crypto, 1);
    var box = $(".crypto_box[data-currency=" + crypto + "]");
    box.find(".deposit_address").text(address)
    $.ajax({
        'url': "/api/historical_transactions/fallback?extended_fetch=true&currency=" + crypto + "&address=" + address,
        'type': 'get',
    }).done(function (response) {
        update_outstanding_ajax(crypto, -1);
        box.find(".internal_error").text("");
        box.find(".deposit_area").show();

        var txs = response['transactions'];
        set_blockchain_data(crypto, 'used_addresses', [address]);
        set_blockchain_data(crypto, 'tx_history', txs);
        update_balance(crypto);
        box.find(".qr").empty().qrcode({render: 'div', width: 100, height: 100, text: address});

        if(txs.length == 0) {
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
        console.log("finished!");
    });
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
    var fiat = $(".fiat_unit").first().text();
    args = {
        extended_fetch: true,
        fiat: fiat,
        currency: crypto
    }

    var addresses_with_activity = [];
    if(addresses.length == 1) {
        args['address'] = addresses[0];
        var mode = "fallback";
    } else {
        args['addresses'] = addresses.join(",");
        var mode = "private5";
    }

    var all_my_addresses = already_tried_addresses.concat(addresses);

    var box = $(".crypto_box[data-currency=" + crypto + "]");

    update_outstanding_ajax(crypto, 1);
    $.ajax({
        url: "/api/historical_transactions/" + mode,
        type: 'get',
        data: args
    }).done(function (response) {
        box.find(".internal_error").text("");
        box.find(".arrow_button").show();
        box.find(".deposit_area").show();

        var txs = response['transactions'];
        concat_blockchain_data(crypto, 'tx_history', txs);
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
                set_blockchain_data(crypto, 'unused_deposit_addresses', unused_address_pool);
            } else if (chain == 'change') {
                set_blockchain_data(crypto, 'unused_change_addresses', unused_address_pool);
            }
            concat_blockchain_data(crypto, 'used_addresses', all_used);
            return // stop iteration
        } else {
            fetch_used_addresses(crypto, chain, needs_to_go, all_tried, all_used);
        }
    }).fail(function(jqXHR, textStatus, errorThrown) {
        var error = errorThrown || "Network Error";
        if(jqXHR.responseJSON) {
            error = jqXHR.responseJSON.error
        }

        ui_set_error(crypto, error);

    }).always(function() {
        var outstanding = update_outstanding_ajax(crypto, -1);
        if (outstanding == 0 && !box.find(".internal_error").text()) {
            remove_duplicates_from_history(crypto);
            set_ui(crypto);
        }
    })
}

function rotate_deposit(crypto, up) {
    var pool = get_blockchain_data(crypto, 'unused_deposit_addresses');
    set_blockchain_data(crypto, 'unused_deposit_addresses', arrayRotate(pool, up));
    return pool[0];
}

function load_crypto(crypto, force) {
    if(get_blockchain_data(crypto, 'tx_history') && !force) {
        set_ui(crypto);
        return;
    }
    set_blockchain_data(crypto, 'used_addresses', []);
    set_blockchain_data(crypto, 'tx_history', []);

    var box = $(".crypto_box[data-currency=" + crypto + "]");
    box.find(".crypto_balance").text("0.0");
    box.find(".fiat_balance").text("0.0");
    box.find(".internal_error").text("").hide();

    if(single_address_cryptos.indexOf(crypto) == -1) {
        fetch_used_addresses(crypto, 'deposit', 10, [], []);
        fetch_used_addresses(crypto, 'change', 10, [], []);
    } else {
        box.find(".arrow_button").hide();
        fetch_history_single_address(crypto, get_deposit_keypair(crypto, 0)[1])
    }
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
    var history = get_blockchain_data(crypto, 'tx_history').sort(function(a, b){
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

        var memo = "";
        if(tx.memos) {
            memo = decrypt_memo(crypto, tx.txid, tx.memos) || "";
        }
        var explorer_link = "<a target='_blank'  href='/tx/" + crypto + "/" + tx.txid + "'>" + tx.txid.substr(0, 8) + "...</a>";
        var history = explorer_link + " " + time + "<br>" + formatted_amount + "<br><span class='existing_memo'>" + memo + "</span>";
        var buttons = "<button class='save_memo' data-txid=" + tx.txid + ">Save</button> <button class='cancel_memo'>Cancel</button><div class='memo_error'></div>"
        var edit_area = "<div class='edit_memo_area'><textarea></textarea>" + buttons + "</div>"
        history_section.append("<div class='touch_for_memo'>" + history + edit_area + "<hr></div>");
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

var total_fiat_balance = 0;
function update_total_fiat_balance() {
    var bal = 0;
    $(".fiat_balance").each(function(i, ele) {
        var this_bal = parseFloat($(ele).text());
        if(this_bal) bal += this_bal;
    });
    $("#total_fiat_balance_container").show();
    var new_balance = bal.toFixed(2);
    //console.log("updating balance from",  total_fiat_balance, "to", new_balance);

    var decimal_places = 2;
    var decimal_factor = decimal_places === 0 ? 1 : Math.pow(10, decimal_places);
    $("#total_fiat_balance").prop('number', total_fiat_balance).animateNumber({
        number: new_balance * decimal_factor,
        numberStep: function(now, tween) {
            var floored_number = Math.floor(now) / decimal_factor,
                target = $(tween.elem);

            if (decimal_places > 0) {
                // force decimal places even if they are 0
                floored_number = floored_number.toFixed(decimal_places);

                // replace '.' separator with ','
                //floored_number = floored_number.toString().replace('.', ',');
            }

            target.text(floored_number);
        }
    },200);
    total_fiat_balance = new_balance;
}

$(function() {
    $('.crypto_box').on("click", ".touch_for_memo", function() {
        //var txid =
        var memo = $(this).find(".existing_memo").text();
        $(this).find(".existing_memo").hide();
        $(this).find(".edit_memo_area textarea").text(memo)
        $(this).find(".edit_memo_area").show();
    });

    $(".crypto_box").on("click", ".save_memo", function(event) {
        event.stopPropagation(); // to avoid triggering ".touch_for_memo" click.
        var save_button = $(this);
        var existing = save_button.parents(".touch_for_memo").find(".existing_memo").text();
        var crypto = save_button.parents(".crypto_box").data("currency");
        var message = save_button.parent().find("textarea").val();
        var txid = save_button.data('txid');

        if(message.length > 713) {
            // 713 corresponds to AES encrypted size of just under 1000 bytes. (common limit for memo severs)
            save_button.siblings(".memo_error").text("Memo too long")
            return
        }

        if(!message && !existing) {
            // no existing memo and textbox was blank, treat as cancel button click
            save_button.siblings(".cancel_memo").click();
            return
        } else if(!message && existing) {
            message = ""; // Will end up a "Please Delete" sent to server
        }

        var spinner_classes = save_button.parents(".crypto_box").find(".spinner").first().attr('class');
        var spinner = "<div class='" + spinner_classes + "' style='width: 12px; height: 12px'></div>";
        save_button.siblings(".memo_error").html(spinner);

        save_memo(message, crypto, txid, function(response) {
            if(response == "OK") {
                save_button.parents(".touch_for_memo").find(".existing_memo").text(message).show();
                save_button.parents(".edit_memo_area").hide();
                save_button.siblings(".memo_error").text("");
            } else {
                save_button.siblings(".memo_error").text(response || "Error");
            }
        });
    });

    $(".crypto_box").on("click", ".cancel_memo", function(event) {
        event.stopPropagation(); // to avoid triggering ".touch_for_memo" click.
        $(this).parents(".touch_for_memo").find(".existing_memo").show();
        $(this).parents(".edit_memo_area").hide();
    });

    $(".cancel_button").click(function() {
        var box = $(this).parent().parent();
        switch_section(box, "receive");
    });

    $(".switch_to_history").click(function() {
        var box = $(this).parent().parent();
        var crypto = box.data('currency');

        switch_section(box, "history");
    });

    $(".refresh_crypto").click(function() {
        var crypto = $(this).parent().parent().data('currency');
        load_crypto(crypto, true);
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

            get_sweep_utxos(crypto, sweep_address, function(utxos) {
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
            $(this).css({color: 'black'});
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

        utxos[crypto] = get_utxos2(crypto);
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
                var withdraw_crypto = box.find(".withdraw_code").first().text();
                error_area.css({color: 'red'}).text(
                    "Deposit larger than maximum of " + max + " " + withdraw_crypto.toUpperCase()
                );
            } else if(deposit && deposit < min) {
                box.find(".exchange_amount").css({color: 'red'});
                box.find(".submit_exchange").attr('disabled', 'disabled');
                var withdraw_crypto = box.find(".withdraw_code").first().text();
                error_area.css({color: 'red'}).text(
                    "Deposit lower than minimum of " + min + " " + withdraw_crypto.toUpperCase()
                );
            } else {
                box.find(".exchange_amount").css({color: 'black'});
                box.find(".submit_exchange").removeAttr('disabled');
                error_area.css({color: 'black'}).text('');
            }
        });

        box.find(".submit_exchange").unbind('click').click(function() {
            var deposit_amount = parseFloat(box.find(".deposit.exchange_amount").val());
            var deposit_satoshi = parseInt(deposit_amount * 1e8);
            var withdraw_code = box.find(".withdraw_code").first().text().toLowerCase();
            var optimal_fee_per_kb = parseFloat(box.find(".optimal_fee_per_kb").text());
            var withdraw_amount = parseFloat(box.find(".withdraw.exchange_amount").val());
            var withdraw_address = get_blockchain_data(withdraw_code, 'unused_deposit_addresses')[0];

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
                concat_blockchain_data(withdraw_code, 'used_addresses', [withdraw_address]);
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

        utxos[crypto] = get_utxos2(crypto);
        get_optimal_fee(crypto, box.find(".optimal_fee_rate_per_byte"));

        box.find(".submit_send").unbind('click').click(function() {
            var sending_address = box.find(".sending_recipient_address").val();
            var sending_amount = parseFloat(box.find(".sending_crypto_amount").val());
            var fee_multiplier = parseFloat(box.find(".send_part .fee_selector:checked").val());

            var tx = make_tx(crypto, [[sending_address, parseInt(sending_amount * 1e8)]], fee_multiplier);

            push_tx(crypto, tx, function(response) {
                switch_section(box, 'receive');
            }, function(error_msg) {
                box.find(".send_error_area").text(error_msg).css({color: 'red'});
            }, sending_amount * -1);
        });
    });

    // The below two functions get called whenever the user changes the fiat,
    // crypto amount, or address field in the sending section.

    $(".sending_recipient_address").keyup(function(event) {
        var sending_address = $(this).val();
        var box = $(this).parents('.crypto_box');
        var crypto = box.data('currency');

        if(!validate_address(crypto, sending_address)) {
            box.find(".submit_send").attr('disabled', 'disabled');
            box.find(".send_error_area").text("Invalid Sending Address").css({color: 'red'});
            $(this).css({color: 'red'});
        } else {
            box.find(".submit_send").removeAttr('disabled');
            box.find(".send_error_area").text("").css({color: 'inherit'});
            $(this).css({color: 'black'});
        }
    });

    $(".sending_fiat_amount, .sending_crypto_amount").keyup(function(event) {
        if(event.keyCode < 0x20 && event.keyCode != 8 && event.keyCode != 46) {
            return // non printable char pressed (tab, shift, del, etc)
        }
        var box = $(this).parents('.crypto_box');
        var which = "fiat";
        if($(this).hasClass("sending_crypto_amount")) {
            which = "crypto";
        }

        var crypto = box.data('currency');
        var value_entered = parseFloat($(this).val());

        //console.log(crypto, exchange_rates, box);
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
            box.find(".send_error_area").text("Amount exceeds balance").css({color: 'red'});
        } else {
            box.find(".sending_fiat_amount, .sending_crypto_amount").css({color: 'black'});
            box.find(".submit_send").removeAttr('disabled');
            box.find(".send_error_area").text("").css({color: 'inherit'});
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


function test_counterparty() {
    try {

        hex = "01000000014330a448667526595512e6da39b77d3f3aaa78b82e06176f5f368101e82594f8020000001976a914ad44fd5f413830597f94896600574d68d63e7a1b88acffffffff0336150000000000001976a91443878e562582fc0201cac32258bd696ee1cf40e588ac00000000000000001e6a1c40029655dfedd4425bfba0441cec6ec532ab25d38052c542d3ba5b854dc70000000000001976a914ad44fd5f413830597f94896600574d68d63e7a1b88ac00000000";
        tx = new bitcore.Transaction(hex);
        console.log(tx.toObject());
        tx.sign('KzWsS4UaUaCfUbrtg1kx2L8FSr8iH3RPTdxC8pyFwYtYc9e7bKNG')


    } catch(e) {
      console.log(e.stack);
    }

}

function ui_set_error(crypto, error) {
    var box = $(".crypto_box[data-currency=" + crypto + "]");
    box.find(".internal_error").text(error).show();
    box.find(".switch_to_send").hide();
    box.find(".switch_to_exchange").hide();
    box.find(".switch_to_history").hide();
    box.find(".switch_to_sweep").hide();
    box.find(".arrow_button").hide();
    box.find(".deposit_area").hide();
    box.find(".qr").empty();
}

function set_ui(crypto) {
    var box = $(".crypto_box[data-currency=" + crypto + "]");
    box.find(".spinner").first().hide();
    box.find(".internal_error").hide();
    $("#loading_screen").hide();
    update_balance(crypto);

    var first_address = get_blockchain_data(crypto, 'unused_deposit_addresses')[0];
    box.find(".receive_part").show();
    box.find(".switch_to_sweep").show();
    box.find(".deposit_address").text(first_address);
    box.find(".qr").empty().qrcode({render: 'div', width: 100, height: 100, text: first_address});

    if(get_blockchain_data(crypto, 'used_addresses').length == 0) {
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

    $.each(get_blockchain_data(crypto, 'tx_history'), function(i, tx) {
        if (tx.confirmations == 0) {
            //console.log("unconfirmed found in history!", crypto);
            var amount = my_amount_for_tx(crypto, tx);
            follow_unconfirmed(crypto, tx.txid, amount);
        }
    });
}

function my_privkeys_from_txid(crypto, txid) {
    // Given a txid, return all privkeys in terms of sorting alphabetical.
    var found_tx = undefined;
    $.each(get_blockchain_data(crypto, 'tx_history'), function(i, tx) {
        if(tx.txid == txid) {
            found_tx = tx;
        }
    });
    var my_addresses = get_blockchain_data(crypto, 'used_addresses');
    var my_matched_privkeys = [];

    $.each(found_tx.inputs.concat(found_tx.outputs), function(i, item) {
        $.each(my_addresses, function(i, address) {
            if(item.address == address) {
                my_matched_privkeys.push(get_privkey(crypto, address));
            }
        });
    });
    return my_matched_privkeys.sort();
}

function save_memo(message, crypto, txid, callback) {
    var priv = my_privkeys_from_txid(crypto, txid)[0];
    if(message) {
        var encrypted_text = CryptoJS.AES.encrypt("BIPXXX" + message, priv).toString();
    } else {
        var encrypted_text = "Please Delete";
    }
    var pk = bitcore.PrivateKey.fromWIF(priv);
    var sig = Message(encrypted_text).sign(pk).toString();

    $.ajax({
        url: "/memo",
        type: "post",
        data: {
            encrypted_text: encrypted_text,
            signature: sig,
            currency: crypto,
            txid: txid,
            pubkey: pk.toPublicKey().toString()
        }
    }).done(function(response) {
        // after successful submitting of memo to memo server, save to localStorage
        // so a page refresh will redraw the memo.
        update_history_with_memo(crypto, txid, encrypted_text)
        callback(response);
    }).fail(function(jqXHR, textStatus, errorThrown) {
        console.log("errror");
        callback("Error from memo server: " + jqXHR.responseJSON['error']);
    });
}

function decrypt_memo(crypto, txid, encrypted_memos) {
    // given a list of encrypted memos and a txid, decrypt each one
    // and return the result as soon as one is found.
    var my_keys = my_privkeys_from_txid(crypto, txid);
    var match = undefined;
    $.each(encrypted_memos, function(i, encrypted_memo) {
        $.each(my_keys, function(i, priv){
            try {
                var decrypted_attemp = CryptoJS.AES.decrypt(encrypted_memo, priv).toString(CryptoJS.enc.Utf8);
            } catch(e) { // sometimes failed decrypts attempts result in UTF8 failures.
                var decrypted_attemp = "";
            }
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

function update_history_with_memo(crypto, txid, memo) {
    // Goes through the localStorage and updates the tx_history to include the
    // new memo (or deletes existing memo).
    var history = get_blockchain_data(crypto, "tx_history");
    $.each(history, function(i, tx){
        if(tx.txid == txid) {
            if(memo) {
                tx.memos = [memo];
            } else {
                tx.memos = [];
            }
        }
    });
    set_blockchain_data(crypto, "tx_history", history);
}
