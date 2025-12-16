from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="sessionstate",
            name="mode",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
    ]




