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

$(function() {
    $("#wallet_settings").click(function(event) {
        event.preventDefault();
        $("#mnemonic_disp").text(raw_mnemonic);
        $("#settings_part").show();
        $("#money_part").hide();
    });

    $("#cancel_settings").click(function() {
        $("#money_part").show();
        $("#settings_part").hide();
    });

    $("#save_settings_button").click(function(event) {
        event.preventDefault();
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

        form.find(".spinner").show();

        $.ajax({
            url: '/wallet/save_settings',
            type: 'post',
            data: settings,
        }).done(function(response) {
            $("#money_part").show();
            settings.show_wallet_list = swl; // replace comma seperated string with list
            fill_in_settings(response.settings);
            if(response.exchange_rates) {
                exchange_rates = response.exchange_rates[0];
                refresh_fiat();
            }
            $("#settings_part").hide();
        }).fail(function(jqXHR, errorText) {
            if(jqXHR.responseJSON) {
                var error_text = jqXHR.responseJSON.error
            } else {
                var error_text = errorText;
            }
            form.find(".error_area").css({color: 'red'}).text(error_text);
        }).always(function() {
            form.find(".spinner").hide();
        });
    });
});
