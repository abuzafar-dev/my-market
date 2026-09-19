from django.db import migrations, models


def pct_to_amount(apps, schema_editor):
    """Turn each product's old percentage into so'm, using its latest batch
    (sale price - cost). Products that never had a batch start at 0."""
    Product = apps.get_model("catalog", "Product")
    Batch = apps.get_model("catalog", "Batch")
    for product in Product.objects.all():
        batch = Batch.objects.filter(product=product).order_by("-received_at").first()
        if batch is not None:
            product.markup_amount = max(int(batch.sale_price - batch.cost_price), 0)
            product.save(update_fields=["markup_amount"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_alter_batch_cost_price_alter_batch_qty_initial_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="markup_amount",
            field=models.PositiveBigIntegerField(default=0, verbose_name="Ustama (so'm)"),
        ),
        migrations.RunPython(pct_to_amount, migrations.RunPython.noop),
        migrations.RemoveField(model_name="product", name="markup_pct"),
    ]
