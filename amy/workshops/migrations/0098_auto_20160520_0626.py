# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2016-05-20 11:26
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.db.models.functions import Length


def migrate_language(apps, schema_editor):
    """Convert EventRequest.language string to key"""
    EventRequest = apps.get_model('workshops', 'EventRequest')
    Language = apps.get_model('workshops', 'Language')
    english = Language.objects.get(name='English')
    for request in EventRequest.objects.all():
        # Get the most precisely matching languages
        language = Language.objects.filter(name__icontains=request.language)\
                .order_by(Length('name')-len(request.language)).first()
        if not language:
            language = english
        request.language_new = language
        request.save()


class Migration(migrations.Migration):

    dependencies = [
        ('workshops', '0097_auto_20160519_0739'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventrequest',
            name='language_new',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='workshops.Language', verbose_name='What human language do you want the workshop to be run in?'),
        ),
        migrations.RunPython(migrate_language),
        migrations.RemoveField(
            model_name='eventrequest',
            name='language',
        ),
        migrations.RenameField(
            model_name='eventrequest',
            old_name='language_new',
            new_name='language',
        ),
    ]
