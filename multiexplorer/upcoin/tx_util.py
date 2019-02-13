import datetime
import random

from bitcoin import ecdsa_verify, ecdsa_recover, ecdsa_sign, pubtoaddr

class InvalidSignature(Exception):
    pass

class InvalidAmounts(Exception):
    pass

def _cut_to_8(amount):
    "Cut decimals to 8 places"
    return float("%.8f" % amount)

def _process_outputs(outputs, timestamp):
    outs = []
    total_out = 0
    for out in sorted(outputs, key=lambda x: x[0]):
        address, amount = out
        if amount <= 0:
            raise InvalidAmounts("Output can't be zero or negative")
        total_out += _cut_to_8(amount)
        outs.append("%s,%s" % (address, amount))

    outs.append(timestamp)
    return total_out, ";".join(outs)

def make_transaction(inputs, outputs):
    timestamp = datetime.datetime.now().isoformat()
    out_total, out_msg = _process_outputs(outputs, timestamp)

    tx = {'inputs': [], 'outputs': [], 'timestamp': timestamp}

    in_total = 0
    for in_ in inputs:
        address, amount, privkey = in_
        if amount <= 0:
            raise InvalidAmounts("Input can't be zero or negative")

        msg = "%s%s%s" % (address, _cut_to_8(amount), out_msg)
        sig = ecdsa_sign(msg, privkey)
        in_total += amount
        tx['inputs'].append([address, amount, sig])

    if in_total < out_total:
        raise InvalidAmounts("Not enough inputs for outputs")

    random.shuffle(outputs)
    tx['outputs'] = outputs
    return tx

def validate_transaction(tx):
    out_total, out_msg = _process_outputs(tx['outputs'], tx['timestamp'])

    in_total = 0
    for i, input in enumerate(tx['inputs']):
        address, amount, sig = input
        if amount <= 0:
            raise InvalidAmounts("Input %s can't be zero or negative" % i)

        message = "%s%s%s" % (address, amount, out_msg)
        in_total += _cut_to_8(amount)
        try:
            pubkey = ecdsa_recover(message, sig)
        except:
            raise InvalidSignature("Signature %s not valid" % i)

        valid_sig = ecdsa_verify(message, sig, pubkey)
        valid_address = pubtoaddr(pubkey) == address
        if not valid_sig or not valid_address:
            raise InvalidSignature("Signature %s not valid" % i)

    if in_total < out_total:
        raise InvalidAmounts("Input amount does not exceed output amount")

    return True


if __name__ == '__main__':

    # testing make_transaction makes a valid transaction
    i = [
        ['18pvhMkv1MZbZZEncKucAmVDLXZsD9Dhk6', 3.2, 'KwuVvv359oft9TfzyYLAQBgpPyCFpcTSrV9ZgJF9jKdT8jd7XLH2'],
        ['14ZiHtrmT6Mi4RT2Liz51WKZMeyq2n5tgG', 0.5, 'KxWoW9Pj45UzUH1d5p3wPe7zxbdJqU7HHkDQF1YQS1AiQg9qeZ9H']
    ]
    o = [['16ViwyAVeKtz4vbTXWRSYgadT5w3Rj3yuq', 2.2],['18pPTxvTc9rJZfD2tM1bNYHFhAcZjgqEdQ', 1.4]]
    assert validate_transaction(make_transaction(i, o))

    # testing invalid signature fails
    fail = 0
    bad_sig = make_transaction(i, o)
    bad_sig['inputs'][0][2] = "23784623kjhdfkjashdfkj837242387"
    try:
        validate_transaction(bad_sig)
    except InvalidSignature:
        fail += 1
    assert fail == 1, "Invalid Signature not happening when sig is edited"

    # testing changing values within already made transaction fails validation
    fail = 0
    bad_sig = make_transaction(i, o)
    bad_sig['inputs'][0][1] = 0.2
    try:
        validate_transaction(bad_sig)
    except InvalidSignature:
        fail += 1
    assert fail == 1, "Invalid Signature not happening when amount is changed"

    # testing make_transaction fails when you make a tx with more outputs than inputs
    fail = 0
    bad_o = [['16ViwyAVeKtz4vbTXWRSYgadT5w3Rj3yuq', 2.2],['18pPTxvTc9rJZfD2tM1bNYHFhAcZjgqEdQ', 9.4]]
    try:
        make_transaction(i, bad_o)
    except InvalidAmounts:
        fail += 1
    assert fail == 1, "Invalid Amount not happening when outputs exceed inputs when making new trasnaction"

    # testing make_transaction fails when you add a zero input
    fail = 0
    bad_o = [['16ViwyAVeKtz4vbTXWRSYgadT5w3Rj3yuq', 0],['18pPTxvTc9rJZfD2tM1bNYHFhAcZjgqEdQ', 9.4]]
    try:
        make_transaction(i, bad_o)
    except InvalidAmounts:
        fail += 1
    assert fail == 1, "Invalid Amount not happening when zero input is tried"

    # testing make_transaction fails when you add a negative input
    fail = 0
    bad_o = [['16ViwyAVeKtz4vbTXWRSYgadT5w3Rj3yuq', -42.07],['18pPTxvTc9rJZfD2tM1bNYHFhAcZjgqEdQ', 9.4]]
    try:
        make_transaction(i, bad_o)
    except InvalidAmounts:
        fail += 1
    assert fail == 1, "Invalid Amount not happening when negative input is tried"

    # testing transaction with valid signatures, but invalid amounts are caught as invalid
    fail = 0
    bad_tx = {
        'inputs': [
            ['18pvhMkv1MZbZZEncKucAmVDLXZsD9Dhk6',3.2,'ILgSi/FsQX2pL5MPoqxvVOAk5o8Njl7a8+ruXXXgU4UIfMyYXx+yytSevMD55ZNceC+1ReVWZgXuFu8iUtOkz2k='],
            ['14ZiHtrmT6Mi4RT2Liz51WKZMeyq2n5tgG',0.5,'IEcFAR6XEdvNmivQDrCEg1DBMiYkwGR+KgB3sVZXdcVTbBD8qfR310m/p/Q5UFRFQ57Cc2mnY+bw8Qr0GQge8So=']
        ],
        'outputs': [
            ['18pPTxvTc9rJZfD2tM1bNYHFhAcZjgqEdQ', 9.4],
            ['16ViwyAVeKtz4vbTXWRSYgadT5w3Rj3yuq', 2.2]
        ],
        'timestamp': '2019-02-13T19:14:27.882253'
    }

    try:
        validate_transaction(bad_tx)
    except InvalidAmounts:
        fail += 1
    assert fail == 1, "Invalid Amount not happening when outputs exceed inputs when validating"

    ################################################################
    fail = 0
    bad_tx = {
        'inputs': [
            ['18pvhMkv1MZbZZEncKucAmVDLXZsD9Dhk6',3.2,'H/vTjUELpBg7uB08QOprZCxkbnZTMefq5VJqgZPzzpLtFeBKClAFEPhzYtYQl5tcK6oq0V+GqIrE8dPUR2teLSg='],
            ['14ZiHtrmT6Mi4RT2Liz51WKZMeyq2n5tgG',0.5,'H5qfLufve25jEf8H2qydWKPG9haSgrFfNYct0G9pmqDZeq1fM1fdZzoMJ8e2H9YMVr6t9wpgJpYwEoWA4I4gJl8=']
        ],
        'outputs': [
            ['18pPTxvTc9rJZfD2tM1bNYHFhAcZjgqEdQ', -9.4],
            ['16ViwyAVeKtz4vbTXWRSYgadT5w3Rj3yuq', 2.2]
        ],
        'timestamp': '2019-02-13T19:47:07.354060'
    }
    try:
        validate_transaction(bad_tx)
    except InvalidAmounts:
        fail += 1
    assert fail == 1, "Invalid Amount not happening when outputs is negative when validating"

    print("all tests pass")
