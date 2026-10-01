from django.urls import path
from core.views import (
    landing_page, minha_home, adicionar_produto, 
    editar_produto, realizar_venda, relatorios, fazer_login, fazer_logout,cadastrar_usuario,exportar_csv,historico_vendas,auto_registro
)

urlpatterns = [
    path('', landing_page, name='landing_page'),
    path('sistema/', minha_home, name='minha_home'),
    path('novo/', adicionar_produto, name='adicionar_produto'),
    path('editar/<int:produto_id>/', editar_produto, name='editar_produto'),
    path('registrar/', auto_registro, name='auto_registro'),
    path('vender/<int:produto_id>/', realizar_venda, name='realizar_venda'),
    path('relatorios/', relatorios, name='relatorios'),
    path('login/', fazer_login, name='login'),
    path('logout/', fazer_logout, name='logout'),
    path('usuarios/novo/', cadastrar_usuario, name='cadastrar_usuario'),
    path('relatorios/exportar/', exportar_csv, name='exportar_csv'),
    path('historico/', historico_vendas, name='historico_vendas'),
]