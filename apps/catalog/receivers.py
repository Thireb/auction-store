def update_sold_out(sender, variant, **kwargs):
    variant.product.update_sold_out()
