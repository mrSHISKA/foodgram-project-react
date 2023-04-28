import csv

from django.core.management import BaseCommand

from recipes.models import Ingredient


class Command(BaseCommand):
    def handle(self, *args, **options):
        file = open('../data/ingredients.csv', 'r', encoding='utf-8')
        reader = csv.reader(file)
        count_data = 0

        for row in reader:
            ingredient, data = Ingredient.objects.get_or_create(
                name=row[0],
                measurement_unit=row[1]
            )
            if data:
                count_data += 1
        if count_data > 0:
            print(f'импортировано {count_data} ингредиентов')
        else:
            print('объекты уже существуют')
