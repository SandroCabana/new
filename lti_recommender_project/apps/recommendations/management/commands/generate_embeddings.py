"""
Comando Django para generar embeddings de recursos educativos.
Uso: python manage.py generate_embeddings [--force]
"""

from django.core.management.base import BaseCommand
from lti_recommender_project.apps.recommendations.services.embedding_service import get_embedding_service


class Command(BaseCommand):
    help = 'Genera embeddings semánticos para todos los recursos educativos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenera embeddings incluso si ya existen',
        )

    def handle(self, *args, **options):
        force_update = options.get('force', False)
        
        self.stdout.write(self.style.WARNING('Iniciando generación de embeddings...'))
        self.stdout.write(self.style.NOTICE('Este proceso puede tardar varios minutos dependiendo del volumen de datos.'))
        
        if force_update:
            self.stdout.write(self.style.WARNING('Modo FORCE: Regenerando todos los embeddings'))
        
        try:
            # Obtener el servicio de embeddings
            embedding_service = get_embedding_service()
            
            # Generar embeddings
            updated, failed = embedding_service.update_resource_embeddings(force_update=force_update)
            
            # Mostrar resultados
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Proceso completado:\n'
                    f'  - Recursos actualizados: {updated}\n'
                    f'  - Recursos fallidos: {failed}'
                )
            )
            
            if failed > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠ Hubo {failed} recursos con errores. Revisa los logs para más detalles.'
                    )
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n✗ Error durante la generación de embeddings: {e}')
            )
            raise
