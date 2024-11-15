# Generated by Django 3.2.10 on 2024-10-05 08:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customerdetails',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
        migrations.AlterField(
            model_name='customerdetails',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=7, null=True),
        ),
    ]
