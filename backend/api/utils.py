
from django.db.models import Sum
from recipes.models import IngredientRecipe


def get_ingredients_in_cart(user):
    cart = IngredientRecipe.objects.filter(
        recipe__cart__user=user).values_list(
        'ingredient__name',
        'ingredient__measurement_unit'
    ).annotate(sum_amount=Sum('amount'))
    ingredient_list = []
    for ingredient in cart:
        name, unit, amount = ingredient
        ingredient_list.append(f'{name} {amount} {unit}\n')
    return ingredient_list
