# Generated by Django 3.2 on 2023-04-25 19:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0007_rename_favorites_list_favorite'),
    ]

    operations = [
        migrations.RenameField(
            model_name='recipe',
            old_name='Ingredients',
            new_name='ingredients',
        ),
    ]
