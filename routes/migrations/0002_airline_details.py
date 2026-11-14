from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


def fill_slugs(apps, schema_editor):
    Airline = apps.get_model("routes", "Airline")
    used = set()
    for a in Airline.objects.order_by("pk"):
        base = slugify(a.name.replace(" Airlines", "").replace(" Air Lines", "")) or "airline"
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        a.slug = slug
        a.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [("routes", "0001_initial")]

    operations = [
        migrations.AddField(model_name="airline", name="slug", field=models.SlugField(max_length=80, null=True, db_index=False)),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
        migrations.AlterField(model_name="airline", name="slug",
                              field=models.SlugField(max_length=80, unique=True, help_text="Page address, /airlines/<slug>/")),
        migrations.AddField(model_name="airline", name="code", field=models.CharField(blank=True, max_length=3, verbose_name="IATA code")),
        migrations.AddField(model_name="airline", name="website", field=models.URLField(blank=True)),
        migrations.AddField(model_name="airline", name="parent", field=models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="brands", to="routes.airline",
            help_text="For a regional brand, the main airline whose page it appears on")),
    ]
