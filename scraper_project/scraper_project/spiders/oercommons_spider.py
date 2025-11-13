# scraper_project/spiders/oer_commons_detailed.py
import scrapy
import re

class OERCommonsDetailedSpider(scrapy.Spider):
    name = 'oer_commons_detailed'
    
    start_urls = ['https://www.oercommons.org/browse?batch_size=100']
    
    def parse(self, response):
        # Enlaces a recursos detallados
        resource_links = response.css('.item-title a::attr(href)').getall()
        
        for link in resource_links:
            yield response.follow(link, self.parse_resource_detail)
        
        # Paginación
        next_page = response.css('.pager-next a::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_resource_detail(self, response):
        """Extraer información detallada de cada recurso"""
        
        yield {
            'titulo': response.css('h1.page-title::text').get('').strip(),
            'descripcion': ' '.join(response.css('.field-description .field-item::text').getall()).strip(),
            'autor': response.css('.field-authors .field-item::text').get(),
            'institucion': response.css('.field-publisher .field-item::text').get(),
            'niveles_educativos': response.css('.field-educational-level .field-item::text').getall(),
            'materias': response.css('.field-subject .field-item a::text').getall(),
            'palabras_clave': response.css('.field-keywords .field-item a::text').getall(),
            'licencia': response.css('.field-license .field-item::text').get(),
            'tipo_recurso': response.css('.field-material-type .field-item::text').get(),
            'fecha_publicacion': response.css('.field-date-created .field-item::text').get(),
            'idioma': response.css('.field-language .field-item::text').get(),
            'url_recurso': response.css('.field-resource-url a::attr(href)').get(),
            'url_oer': response.url,
            'evaluaciones': self.extraer_evaluaciones(response),
            'estandares': self.extraer_estandares(response),
        }

    def extraer_evaluaciones(self, response):
        """Extraer información de evaluaciones si existe"""
        return {
            'puntuacion': response.css('.rating .average-rating::text').get(),
            'comentarios': response.css('.comment .comment-body::text').getall()
        }

    def extraer_estandares(self, response):
        """Extraer estándares educativos"""
        return response.css('.field-standards .field-item::text').getall()