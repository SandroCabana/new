import scrapy
import re
import hashlib


class OERCommonsDetailedSpider(scrapy.Spider):
    name = 'oer_commons_detailed'
    
    start_urls = ['https://www.oercommons.org/browse?batch_size=50']
    
    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 30,
        'DOWNLOAD_DELAY': 2,
    }
    
    def parse(self, response):
        """Parse la página de listado"""
        self.logger.info(f"Parsing browse page: {response.url}")
        
        # Enlaces a recursos detallados
        resource_links = response.css('.item-title a::attr(href), .search-result-title a::attr(href), h3 a::attr(href)').getall()
        
        self.logger.info(f"Found {len(resource_links)} resource links")
        
        for link in resource_links[:10]:  # Limitar a 10 por página
            yield response.follow(link, self.parse_resource_detail)
        
        # Paginación
        next_page = response.css('.pager-next a::attr(href), a[rel="next"]::attr(href)').get()
        if next_page:
            self.logger.info(f"Following next page: {next_page}")
            yield response.follow(next_page, self.parse)

    def parse_resource_detail(self, response):
        """Extraer información detallada de cada recurso"""
        try:
            titulo = response.css('h1.page-title::text, h1::text').get('').strip()
            
            if not titulo:
                self.logger.warning(f"No title found for {response.url}")
                return
            
            descripcion = ' '.join(response.css('.field-description .field-item::text, .description::text, p::text').getall()).strip()
            
            # Generar resource_id único
            resource_id = hashlib.md5(response.url.encode()).hexdigest()
            
            # Extraer URL del recurso
            url_recurso = response.css('.field-resource-url a::attr(href)').get() or response.url
            
            # Determinar tipo de recurso
            tipo_material = response.css('.field-material-type .field-item::text').get()
            resource_type = self.determinar_tipo_recurso(tipo_material, titulo, descripcion)
            
            # Extraer materias/tags
            materias = response.css('.field-subject .field-item a::text, .subject::text').getall()
            palabras_clave = response.css('.field-keywords .field-item a::text, .keyword::text').getall()
            tags = ', '.join(set(materias + palabras_clave))
            
            # Nivel educativo
            niveles = response.css('.field-educational-level .field-item::text').getall()
            difficulty = self.estimar_dificultad(niveles, descripcion, titulo)
            
            item = {
                'resource_id': resource_id,
                'title': titulo[:255],
                'description': descripcion[:1000] if descripcion else titulo,
                'url': url_recurso[:500],
                'author': response.css('.field-authors .field-item::text, .author::text').get('OER Commons')[:255],
                'resource_type': resource_type,
                'tags': tags[:500] if tags else 'educación',
                'difficulty_level': difficulty,
                'lti_context_id': None,
                'source': 'OER Commons'
            }
            
            self.logger.info(f"Scraped: {titulo}")
            return item
            
        except Exception as e:
            self.logger.error(f"Error parsing resource detail {response.url}: {e}")
            return None

    def determinar_tipo_recurso(self, tipo_material, titulo, descripcion):
        """Determinar el tipo de recurso"""
        texto = f"{tipo_material} {titulo} {descripcion}".lower()
        
        if any(word in texto for word in ['video', 'youtube', 'vimeo', 'watch']):
            return 'video'
        elif any(word in texto for word in ['pdf', '.pdf', 'document']):
            return 'pdf'
        elif any(word in texto for word in ['quiz', 'test', 'assessment', 'exam']):
            return 'quiz'
        elif any(word in texto for word in ['interactive', 'simulation', 'game', 'tool']):
            return 'tool'
        elif any(word in texto for word in ['article', 'lesson', 'tutorial', 'guide']):
            return 'article'
        else:
            return 'other'

    def estimar_dificultad(self, niveles, descripcion, titulo):
        """Estimar nivel de dificultad"""
        texto = f"{' '.join(niveles)} {titulo} {descripcion}".lower()
        
        if any(word in texto for word in ['advanced', 'university', 'college', 'graduate', 'expert']):
            return 'advanced'
        elif any(word in texto for word in ['intermediate', 'high school', 'secondary']):
            return 'intermediate'
        else:
            return 'beginner'
