from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from api.filters import IngredientFilter, RecipeFilter
from api.paginations import LimitPagination
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (CustomUserSerializer, IngredientSerializer,
                             RecipeReadSerializer, RecipeReadShortSerializer,
                             RecipeWtiteSerializer, SubscribeSerializer,
                             TagSerializer)
from api.utils import get_ingredients_in_cart
from recipes.models import Favorite, Ingredient, Recipe, ShoppingCart, Tag
from users.models import Subscribe

User = get_user_model()


class CustomUserViewSet(UserViewSet):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer

    @action(
        detail=False,
        methods=(['GET']),
        permission_classes=[IsAuthenticated]
    )
    def subscriptions(self, request):
        user = request.user
        subscriptions = User.objects.filter(subscribing__user=user)
        page = self.paginate_queryset(subscriptions)
        serializer = SubscribeSerializer(page, many=True,
                                         context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=(['POST', 'DELETE']),
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, id=None):
        user = request.user
        author = get_object_or_404(User, id=id)
        if request.method == 'POST':
            serializer = SubscribeSerializer(author,
                                             data=request.data,
                                             context={'request': request})
            if serializer.is_valid(raise_exception=True):
                Subscribe.objects.create(user=user, author=author)
            return Response(serializer.data)

        if request.method == 'DELETE':
            if not Subscribe.objects.filter(user=user, author=author).exists():
                return Response('Вы не были на него подписаны',
                                status=status.HTTP_400_BAD_REQUEST)
            subscriptions = get_object_or_404(Subscribe,
                                              user=user,
                                              author=author)

            subscriptions.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IngredientViewSet(ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None


class TagViewSet(ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None


class RecipeViewSet(ModelViewSet):
    queryset = Recipe.objects.all()
    permission_classes = [IsAuthorOrReadOnly]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    pagination_class = LimitPagination

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeWtiteSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def add_recipe(self, user, model, pk):
        if model.objects.filter(user=user, recipe__id=pk).exists():
            return Response('Рецепт уже был добавлен',
                            status=status.HTTP_400_BAD_REQUEST)
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        serializer = RecipeReadShortSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete_recipe(self, user, model, pk):
        recipe = model.objects.filter(user=user,
                                      recipe__id=pk)
        if recipe.exists():
            recipe.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            'Вы пытаетесь удалить рецепт, который уже был удален',
            status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True,
            methods=['POST', 'DELETE'],
            permission_classes=[IsAuthenticated]
            )
    def shopping_cart(self, request, pk):
        if request.method == 'POST':
            return self.add_recipe(request.user, ShoppingCart, pk)
        return self.delete_recipe(request.user, ShoppingCart, pk)

    @action(detail=True,
            methods=['POST', 'DELETE'],
            permission_classes=[IsAuthenticated]
            )
    def favorite(self, request, pk):
        if request.method == 'POST':
            return self.add_recipe(request.user, Favorite, pk)
        return self.delete_recipe(request.user, Favorite, pk)

    @action(detail=False,
            permission_classes=[IsAuthenticated]
            )
    def download_shopping_cart(self, request):
        ingredients_in_cart = get_ingredients_in_cart(request.user)
        if not ingredients_in_cart:
            return Response('Нечего скачивать, корзина пуста',
                            status=status.HTTP_400_BAD_REQUEST)
        response = HttpResponse(ingredients_in_cart, content_type='text/plain')
        response['Content-Disposition'] = ('attachment;'
                                           + 'filename="shopping_cart.txt"')
        return response
