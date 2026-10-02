from django.urls import path, include
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings
from core.views import (
    landing_page, minha_home, adicionar_produto, 
    editar_produto, realizar_venda, relatorios, fazer_login, fazer_logout,cadastrar_usuario,exportar_csv,historico_vendas,auto_registro, adicionar_ao_carrinho, ver_carrinho, remover_do_carrinho, finalizar_venda_carrinho,comprovante_venda,cancelar_venda,gerenciar_caixa,gerenciar_usuarios,alternar_status_usuario
)

urlpatterns = [
    path('', landing_page, name='landing_page'),
    path('admin/', admin.site.urls),
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
    path('carrinho/', ver_carrinho, name='ver_carrinho'),
    path('carrinho/adicionar/<int:produto_id>/', adicionar_ao_carrinho, name='adicionar_ao_carrinho'),
    path('carrinho/remover/<int:produto_id>/', remover_do_carrinho, name='remover_do_carrinho'),
    path('carrinho/finalizar/', finalizar_venda_carrinho, name='finalizar_venda_carrinho'),
    path('carrinho/comprovante/', comprovante_venda, name='comprovante_venda'),
    path('historico/cancelar/<int:venda_id>/', cancelar_venda, name='cancelar_venda'),
    path('caixa/', gerenciar_caixa, name='gerenciar_caixa'),
    path('usuarios/', gerenciar_usuarios, name='gerenciar_usuarios'),
    path('usuarios/toggle/<int:user_id>/', alternar_status_usuario, name='alternar_status_usuario'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)