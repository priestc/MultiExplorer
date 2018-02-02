# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-02-01 22:46
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('multiexplorer', '0008_auto_20170503_0700'),
    ]

    operations = [
        migrations.CreateModel(
            name='IPTracker',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip', models.CharField(max_length=64)),
                ('last_unbanned', models.DateTimeField(default=django.utils.timezone.now)),
                ('hits', models.IntegerField()),
            ],
            options={
                'get_latest_by': 'last_unbanned',
            },
        ),
    ]
