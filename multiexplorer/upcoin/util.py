import datetime
from bitcoin import ecdsa_sign, pubtoaddr

def make_signature(input_address, input_priv, input_amount, outputs):
    message = "%s%s%s" % (input_address, input_amount, outputs)
    return ecdsa_sign(message, input_priv)

def make_transaction(inputs, outputs):
    """
    EX:
    [
        ['18pvhMkv1MZbZZEncKucAmVDLXZsD9Dhk6', 3.2, 'KwuVvv359oft9TfzyYLAQBgpPyCFpcTSrV9ZgJF9jKdT8jd7XLH2'],
        ['14ZiHtrmT6Mi4RT2Liz51WKZMeyq2n5tgG', 0.5, 'KxWoW9Pj45UzUH1d5p3wPe7zxbdJqU7HHkDQF1YQS1AiQg9qeZ9H'],
    ],
    [
        ['16ViwyAVeKtz4vbTXWRSYgadT5w3Rj3yuq', 2.2],
        ['18pPTxvTc9rJZfD2tM1bNYHFhAcZjgqEdQ', 1.4]
    ]
    }
    """
    timestamp = datetime.datetime.now().isoformat()
    outs = []
    for out in outputs:
        address, amount = out
        outs.append("%s,%s" % (address, amount))

    outs.append(timestamp)
    outs = ";".join(outs)

    tx = {'inputs': [], 'outputs': [], 'timestamp': timestamp}
    for in_ in inputs:
        address, amount, privkey = in_
        msg = "%s%s%s" % (address, amount, outs)
        sig = ecdsa_sign(msg, privkey)
        tx['inputs'].append([address, amount, sig])

    tx['outputs'] = outputs
    return tx
