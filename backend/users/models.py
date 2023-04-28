from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import UniqueConstraint


class User(AbstractUser):
    email = models.EmailField('Email', max_length=254, unique=True)
    username = models.CharField(
        'Ник', max_length=100,
        unique=True,
        validators=[RegexValidator(regex=r'^[\w.@+-]+\Z')])
    password = models.CharField('Пароль', max_length=100)
    first_name = models.CharField('Имя', max_length=100)
    last_name = models.CharField('Фамилия', max_length=100)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [
        'username',
        'first_name',
        'last_name',
    ]

    class Meta:
        ordering = ['id']
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username


class Subscribe(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscriber',
        verbose_name='подписчик',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscribing',
        verbose_name='Автор',
    )

    class Meta:
        ordering = ['id']
        constraints = [
            UniqueConstraint(fields=['user', 'author'],
                             name='unique_sub')
        ]
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
