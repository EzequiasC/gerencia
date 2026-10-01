from django.contrib import admin
from core.models import Produto

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('name', 'categoria', 'preco', 'quantidade_estoque')
    search_fields = ('name', 'categoria')