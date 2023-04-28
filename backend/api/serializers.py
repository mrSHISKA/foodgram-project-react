import base64

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers, status

from recipes.models import Ingredient, IngredientRecipe, Recipe, Tag
from users.models import Subscribe

User = get_user_model()


class CustomUserSerializer(UserSerializer):
    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name',
            'is_subscribed'
        )

    def get_is_subscribed(self, obj):
        user = self.context.get('request').user
        return (
            user.is_authenticated
            and obj.subscribing.filter(user=user).exists()
        )


class CustomUserCreateSerializer(UserCreateSerializer):
    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name', 'password'
        )


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)

        return super().to_internal_value(data)


class RecipeReadShortSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time',)


class SubscribeSerializer(CustomUserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes', 'recipes_count')
        read_only_fields = ('email', 'username', 'first_name', 'last_name')

    def validate(self, attrs):
        author = self.instance
        user = self.context.get('request').user
        if Subscribe.objects.filter(author=author, user=user).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого пользователя',
                code=status.HTTP_400_BAD_REQUEST
            )
        if user == author:
            raise serializers.ValidationError(
                'Вы пытаетесь подписаться на самого себя',
                code=status.HTTP_400_BAD_REQUEST
            )
        return attrs

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def get_recipes(self, obj):
        all_recipes = obj.recipes.all()
        return RecipeReadShortSerializer(all_recipes, many=True,
                                         read_only=True).data


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')


class IngredientRecipeReadSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit')
    amount = serializers.IntegerField()

    class Meta:
        model = IngredientRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeReadSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = IngredientRecipeReadSerializer(many=True, read_only=True,
                                                 source='ingredients_recipe')
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'name', 'image', 'text', 'ingredients',
            'tags', 'cooking_time', 'is_favorited', 'is_in_shopping_cart'
        )

    def get_is_favorited(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return user.favorites.filter(recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return user.cart.filter(recipe=obj).exists()


class IngredientRecipeWriteSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField()

    class Meta:
        model = IngredientRecipe
        fields = ('id', 'amount')


class RecipeWtiteSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(many=True,
                                              queryset=Tag.objects.all())
    ingredients = IngredientRecipeWriteSerializer(many=True)
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('tags', 'ingredients', 'author', 'name', 'text', 'image',
                  'cooking_time')
        read_only_fields = ('author',)

    def validate(self, attrs):
        ingredients = attrs.get('ingredients', [])
        ingredients_id = []
        if not ingredients:
            raise serializers.ValidationError(
                "ингредиенты обязательны для добавления")
        if not attrs.get('tags'):
            raise serializers.ValidationError("теги обязательны")
        if attrs.get('cooking_time') <= 0:
            raise serializers.ValidationError(
                "время приготовления не может быть <= 0")
        for item in ingredients:
            now_id = item.get('id')
            amount = item.get('amount')
            if now_id not in ingredients_id:
                ingredients_id.append(now_id)
            else:
                raise serializers.ValidationError(
                    "нельзя добавить два одинаковых ингредиента")
            if amount <= 0:
                raise serializers.ValidationError(
                    "количество ингредиентов не может быть <= 0")
        return attrs

    def get_ingredients(self, ingredients, recipe):
        ingredients_recipes = []
        for ingredient in ingredients:
            ingredients_recipes.append(
                IngredientRecipe(
                    ingredient=ingredient.get('id'),
                    recipe=recipe,
                    amount=ingredient.get('amount')
                )
            )
        return ingredients_recipes

    def create(self, validated_data):
        ingredients = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.add(*tags)
        IngredientRecipe.objects.bulk_create(self.create_ingredients
                                             (recipe=recipe,
                                              ingredients=ingredients))
        return recipe

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('ingredients')
        instance.tags.clear()
        instance.tags.add(*tags)
        IngredientRecipe.objects.filter(recipe=instance).delete()
        for field, value in validated_data.items():
            setattr(instance, field, value)
        IngredientRecipe.objects.bulk_create(self.create_ingredients
                                             (recipe=instance,
                                              ingredients=ingredients))
        instance.save()
        return instance

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return RecipeReadSerializer(instance, context=context).data
