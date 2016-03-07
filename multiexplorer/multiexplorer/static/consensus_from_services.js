function guess_currency_from_address(address) {
    // Given an address, guess what currency it is by lookign at the magic byte.
    // returns undefined if it can't find a match.
    var magic_byte = bitcore.encoding.Base58Check(address).buf[0];

    var ret;
    $.each(crypto_data, function(currency, data) {
        if(data['address_version_byte'] == magic_byte) {
            ret = currency;
            return false;
        }
    });
    return ret
}

$("#unspent_outputs_button").click(function(event) {
    event.preventDefault();
    var address = $("input[name=unspent_outputs_input_box]").val();
    var aggregate_container = $("#aggregated_unspent_outputs").empty();
    $("#unspent_outputs .service_call").remove();

    var currency = guess_currency_from_address(address);

    present_results(
        currency, "unspent_outputs", "?address=" + address,
        function(response, matches) {
            if(aggregate_container.children().length == 0) {
                // first response, place it on the aggregate container
                //console.log("first result", response.service_name);
                $.each(response['utxos'], function(i, utxo) {
                    var rows = "";
                    var table = $("<table class='utxo_table'></table>");
                    rows += "<tr><td>Confirmations</td><td class='confirmations'>" + utxo['confirmations'] + "</td></tr>";
                    rows += "<tr><td>Output</td><td class='output'>" + utxo['output'] + "</td></tr>";
                    rows += "<tr><td>Amount</td><td class='amount'>" + utxo['amount'] + "</td></tr>";
                    table.append(rows);
                    aggregate_container.append(table);
                });
            }

            var match_class = matches ? "matches" : "not-matches";
            var match_text = matches ? "Matches" : "No Match";
            return "<span class='final_result " + match_class + "'>" + match_text + "</span>";
        },
        function(response, container) {
            // matches_func, compare existing, returns whether this is in consensus or not.
            var aggregated_utxos = aggregate_container.find(".utxo_table");
            var matches = true;

            //console.log("matches func");

            $.each(response['utxos'], function(i, utxo) {
                var corresponding = $(aggregated_utxos[i]);
                if(corresponding.length == 0) {
                    // first result! nothing to compare to yet. Consider Matched!
                    return false;
                }

                var matched_amount = parseInt(corresponding.find(".amount").text()) == parseInt(utxo['amount']);
                var matched_output = corresponding.find(".output").text() == utxo['output'];

                if(!matched_amount || !matched_output) {
                    matches = false;
                    return false; // stop iterating
                }
            });

            return matches;
        }
    );
});

function present_results(currency, mode, api_args, format_result_func, matches_func) {
    var container = $("#" + mode + "_results");

    $.each(crypto_data[currency][mode], function(i, service_id) {
        // each service for the supported cyurrency
        var info = service_info[service_id];
        var url = info['url'];
        var service_name = info['name'];
        var a = "<a class='service_title' target='_blank' href='" + url + "'> (" + service_id + ') ' + service_name + "</a>";

        var result_selector = "service-" + mode + '-' + service_id;

        container.append(
            $("<div class='service_call'>" + a + "<div class='result " + result_selector + "'>" + spinner + "</div></div>")
        );

        var url = "/api/" + mode + "/" + service_id + api_args;

        $.ajax({
            url: url,
        }).done(function(response) {

            matches = matches_func(response, container);

            var raw_link = "<a target='_blank' href='" + response['url'] + "'>Raw</a>";
            var api_link = "<a target='_blank' href='" + url + "&include_raw=true'>API</a>";
            $("." + result_selector).html(
                format_result_func(response, matches) + '<br>' + raw_link + ' ' + api_link
            );

        }).fail(function(xhr, status, error) {
            // place the error message passed on directly from the service
            var error_msg = xhr.responseJSON['error'];
            $("." + result_selector).html("<span class='error'>Error:" + error_msg + "</span>");
        });
    });
};
