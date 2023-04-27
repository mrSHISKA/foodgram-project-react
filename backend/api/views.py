from api.serializers import (CustomUserSerializer, SubscribeSerializer,
                             TagSerializer, IngredientSerializer,
                             RecipeReadSerializer, RecipeWtiteSerializer,
                             RecipeReadShortSerializer)
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from djoser.views import UserViewSet
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from users.models import Subscribe
from recipes.models import Tag, Ingredient, Recipe, Favorite, ShoppingCart
from api.filters import IngredientFilter, RecipeFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status
from api.permissions import IsAuthorOrReadOnly
from django.http import HttpResponse
from api.paginations import LimitPagination


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
            if user == author:
                return Response('Вы пытаетесь подписаться на самого себя',
                                status=status.HTTP_400_BAD_REQUEST)
            if Subscribe.objects.filter(user=user, author=author).exists():
                return Response('Вы уже подписаны на этого пользователя',
                                status=status.HTTP_400_BAD_REQUEST)
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

    def get_queryset(self):
        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart')
        if is_in_shopping_cart is not None:
            return Recipe.objects.filter(cart__user=self.request.user)
        is_favorited = self.request.query_params.get('is_favorited')
        if is_favorited is not None:
            return Recipe.objects.filter(favorites__user=self.request.user)

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return RecipeReadSerializer
        return RecipeWtiteSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True,
            methods=['POST', 'DELETE'],
            permission_classes=[IsAuthenticated]
            )
    def shopping_cart(self, request, pk):
        if request.method == 'POST':
            user = request.user
            if ShoppingCart.objects.filter(user=user, recipe__id=pk).exists():
                return Response('Рецепт уже в корзине',
                                status=status.HTTP_400_BAD_REQUEST)
            recipe = get_object_or_404(Recipe, id=pk)
            ShoppingCart.objects.create(user=user, recipe=recipe)
            serializer = RecipeReadShortSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            user = request.user
            recipe_in_cart = ShoppingCart.objects.filter(user=user,
                                                         recipe__id=pk)
            if recipe_in_cart.exists():
                recipe_in_cart.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                'Вы пытаетесь удалить рецепт, которого нет в корзине',
                status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False,
            permission_classes=[IsAuthenticated]
            )
    def download_shopping_cart(self, request):
        cart_items = request.user.cart.values_list(
            'recipe__ingredients__name',
            'recipe__ingredients__measurement_unit',
            'recipe__ingredients_recipe__amount')
        cart = {}
        for item in cart_items:
            name, unit, amount = item
            if name in cart:
                current_amount = cart[name]['amount']
                if current_amount is not None:
                    cart[name]['amount'] = current_amount + amount
                else:
                    cart[name]['amount'] = amount
            else:
                cart[name] = {'unit': unit, 'amount': amount}
        if not cart:
            return Response('Нечего скачивать, корзина пуста',
                            status=status.HTTP_400_BAD_REQUEST)

        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = 'attachment; \
                                        filename="shopping_cart.txt"'
        for name, data in cart.items():
            response.write(f'{name} ({data["unit"]}) — {data["amount"]}\n')
        return response

    @action(detail=True,
            methods=['POST', 'DELETE'],
            permission_classes=[IsAuthenticated]
            )
    def favorite(self, request, pk):
        if request.method == 'POST':
            user = request.user
            if Favorite.objects.filter(user=user, recipe__id=pk).exists():
                return Response('Рецепт уже в избранном',
                                status=status.HTTP_400_BAD_REQUEST)
            recipe = get_object_or_404(Recipe, id=pk)
            Favorite.objects.create(user=user, recipe=recipe)
            serializer = RecipeReadShortSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            user = request.user
            recipe_in_cart = Favorite.objects.filter(user=user, recipe__id=pk)
            if recipe_in_cart.exists():
                recipe_in_cart.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response('Вы пытаетесь убрать рецепт из избранного,'
                            + ' которого там нет',
                            status=status.HTTP_400_BAD_REQUEST)
