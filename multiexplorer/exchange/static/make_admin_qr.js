$(function() {
    $(".qr").each(function() {
        var addr = $(this).data('address');
        var opts = {text: addr};
        var size = 200;
        if($(this).data('size') == 'medium') {
            size = 150;
        } else if ($(this).data('size') == 'small') {
            size = 100;
        }
        opts.width = size;
        opts.height = size;
        $(this).qrcode(opts);
    });
});
