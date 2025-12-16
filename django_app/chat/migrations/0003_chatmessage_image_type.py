from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0002_sessionstate_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="image_type",
            field=models.CharField(
                blank=True,
                choices=[("current", "현재 방 사진"), ("reference", "레퍼런스 사진")],
                max_length=20,
                null=True,
            ),
        ),
    ]




