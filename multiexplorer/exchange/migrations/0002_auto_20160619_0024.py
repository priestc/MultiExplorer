# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('exchange', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExchangeAddress',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.now)),
                ('last_kick', models.DateTimeField(default=None, null=True)),
                ('deposit_address', models.CharField(max_length=128)),
                ('exchange_rate', models.FloatField()),
                ('withdraw_address', models.CharField(max_length=128, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='ExchangeMasterKey',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.now)),
                ('xpriv', models.CharField(max_length=120, blank=True)),
                ('from_passphrase', models.TextField(blank=True)),
                ('notes', models.TextField(blank=True)),
                ('utxos', models.TextField()),
            ],
            options={
                'get_latest_by': 'created',
            },
        ),
        migrations.CreateModel(
            name='ExchangeWithdraw',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('deposit_txid', models.TextField()),
                ('withdraw_inputs', models.TextField()),
                ('withdraw_confirmed', models.BooleanField(default=False)),
                ('exchange', models.ForeignKey(to='exchange.ExchangeAddress')),
            ],
        ),
        migrations.AddField(
            model_name='exchangecurrency',
            name='code',
            field=models.CharField(max_length=5, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='exchangecurrency',
            name='fee_percentage',
            field=models.FloatField(default=0.01),
        ),
        migrations.AlterField(
            model_name='exchangecurrency',
            name='currency',
            field=models.IntegerField(choices=[(2147483676, b'vtc - Vertcoin'), (2147483648, b'btc - Bitcoin'), (2147483650, b'ltc - Litecoin'), (2147483654, b'ppc - Peercoin'), (2147483651, b'doge - Dogecoin'), (2147483738, b'myr - MyriadCoin'), (2147483653, b'dash - Dash')]),
        ),
        migrations.AddField(
            model_name='exchangeaddress',
            name='deposit_currency',
            field=models.ForeignKey(related_name='incoming_exchanges', to='exchange.ExchangeCurrency'),
        ),
        migrations.AddField(
            model_name='exchangeaddress',
            name='withdraw_currency',
            field=models.ForeignKey(related_name='outgoing_exchanges', to='exchange.ExchangeCurrency'),
        ),
    ]
