from django.core.management.base import BaseCommand
from core.models import Produto

class Command(BaseCommand):
    help = 'Popula o banco de dados com produtos do setor de bebidas para testes do PDV.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Iniciando o abastecimento do estoque com bebidas...')
        
        bebidas_exemplo = [
            # Cervejas
            {'name': 'Cerveja Heineken Long Neck 330ml', 'categoria': 'bebidas', 'preco_custo': 4.50, 'preco': 8.00, 'quantidade_estoque': 72},
            {'name': 'Cerveja Brahma Duplo Malte Lata 350ml', 'categoria': 'bebidas', 'preco_custo': 2.80, 'preco': 5.00, 'quantidade_estoque': 120},
            {'name': 'Cerveja Amstel Lata 350ml', 'categoria': 'bebidas', 'preco_custo': 2.60, 'preco': 4.50, 'quantidade_estoque': 96},
            {'name': 'Cerveja Corona Extra Long Neck 330ml', 'categoria': 'bebidas', 'preco_custo': 5.00, 'preco': 9.00, 'quantidade_estoque': 48},
            {'name': 'Litrão Stella Artois 970ml', 'categoria': 'bebidas', 'preco_custo': 8.50, 'preco': 14.00, 'quantidade_estoque': 30},

            # Não Alcoólicos / Refrigerantes / Água
            {'name': 'Refrigerante Coca-Cola 2 Litros (Pet)', 'categoria': 'bebidas', 'preco_custo': 7.50, 'preco': 12.00, 'quantidade_estoque': 36},
            {'name': 'Refrigerante Guaraná Antarctica 2L', 'categoria': 'bebidas', 'preco_custo': 6.00, 'preco': 10.00, 'quantidade_estoque': 30},
            {'name': 'Refrigerante Coca-Cola Lata 350ml', 'categoria': 'bebidas', 'preco_custo': 2.50, 'preco': 5.00, 'quantidade_estoque': 48},
            {'name': 'Água Mineral sem Gás 500ml', 'categoria': 'bebidas', 'preco_custo': 1.20, 'preco': 3.00, 'quantidade_estoque': 60},
            {'name': 'Água Tônica Schweppes Lata 350ml', 'categoria': 'bebidas', 'preco_custo': 3.00, 'preco': 6.00, 'quantidade_estoque': 24},

            # Energéticos
            {'name': 'Energético Red Bull Lata 250ml', 'categoria': 'bebidas', 'preco_custo': 6.50, 'preco': 11.00, 'quantidade_estoque': 40},
            {'name': 'Energético Monster Energy Green 473ml', 'categoria': 'bebidas', 'preco_custo': 7.00, 'preco': 13.00, 'quantidade_estoque': 30},

            # Destilados e Outros
            {'name': 'Whisky Johnnie Walker Red Label 1L', 'categoria': 'bebidas', 'preco_custo': 75.00, 'preco': 119.90, 'quantidade_estoque': 12},
            {'name': 'Vodka Smirnoff 998ml', 'categoria': 'bebidas', 'preco_custo': 35.00, 'preco': 59.90, 'quantidade_estoque': 10},
            {'name': 'Gin Tanqueray 750ml', 'categoria': 'bebidas', 'preco_custo': 95.00, 'preco': 149.90, 'quantidade_estoque': 8},
            {'name': 'Gelo em Cubos Pacote 5kg', 'categoria': 'outros', 'preco_custo': 4.00, 'preco': 10.00, 'quantidade_estoque': 25},
        ]

        criados = 0
        for item in bebidas_exemplo:
            produto, created = Produto.objects.get_or_create(
                name=item['name'],
                defaults=item
            )
            if created:
                criados += 1

        self.stdout.write(self.style.SUCCESS(f'Sucesso! {criados} bebidas foram adicionadas ao estoque do PDV.'))