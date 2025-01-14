# Generated by Django 3.2.10 on 2024-10-07 06:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_auto_20241005_1444'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='customerdetails',
            name='api_custome_name_e30eb2_idx',
        ),
        migrations.AddField(
            model_name='customerdetails',
            name='email',
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='customerdetails',
            name='mobile_no',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterUniqueTogether(
            name='customerdetails',
            unique_together={('mobile_no',)},
        ),
        migrations.AddIndex(
            model_name='customerdetails',
            index=models.Index(fields=['mobile_no'], name='api_custome_mobile__13db5d_idx'),
        ),
    ]
