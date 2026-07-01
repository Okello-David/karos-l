from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("occupancy", "0003_occupancy_agreed_price"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="occupancy",
            name="ck_occupancy_end_date_after_start",
        ),
        migrations.AddConstraint(
            model_name="occupancy",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_date__isnull", True), ("end_date__gte", models.F("start_date")), _connector="OR"),
                name="ck_occupancy_end_date_after_start",
            ),
        ),
    ]
