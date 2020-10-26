from django.contrib import admin

from .models import Scope, UserProviderScope


@admin.register(Scope)
class ScopeAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'required', 'grants_access', 'access_type']
    list_filter = ['provider']
    ordering = ['provider', '-required', 'name']


@admin.register(UserProviderScope)
class UserProviderScopeAdmin(admin.ModelAdmin):
    list_display = ['account', 'scope']
    list_filter = ['account']
