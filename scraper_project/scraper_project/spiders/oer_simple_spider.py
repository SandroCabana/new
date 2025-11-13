# scraper_project/spiders/oer_simple_spider.py
import scrapy
from urllib.parse import urljoin, urlencode

class OERSimpleSpider(scrapy.Spider):
    name = 'oer_simple'
    
    # Empezar con menos áreas para prueba
    SUBJECT_AREAS = {
        'mathematics': 'Mathematics',
        'social-science': 'Social Science',
        'computer-science': 'Computer Science'
    }

    def start_requests(self):
        base_url = "https://oercommons.org/courses/"
        
        for subject_slug, subject_name in self.SUBJECT_AREAS.items():
            params = {
                'batch_size': 20,  # Menos recursos por área para prueba
                'f.general_subject': subject_slug
            }
            
            url = f"{base_url}?{urlencode(params)}"
            
            yield scrapy.Request(
                url,
                callback=self.parse_subject,
                meta={'subject_area': subject_name}
            )

    def parse_subject(self, response):
        subject_area = response.meta['subject_area']
        resources = response.css('article.js-index-item')
        
        self.logger.info(f"Área: {subject_area} - Recursos: {len(resources)}")
        
        for resource in resources:
            item = self.extract_basic_data(resource, response)
            if item and item.get('titulo'):
                item['area_tematica'] = subject_area
                yield item

    def extract_basic_data(self, resource, response):
        """Extraer datos básicos del recurso"""
        
        titulo = resource.css('.item-title a::text').get('').strip()
        if not titulo:
            return None
            
        relative_url = resource.css('.item-title a::attr(href)').get()
        resource_url = urljoin(response.url, relative_url) if relative_url else None
        
        # Descripción
        desc_corta = resource.css('.abstract-short p::text').get('')
        desc_larga = resource.css('.abstract-full p::text').get('')
        descripcion = desc_larga or desc_corta
        
        # Materias
        materias = resource.css('a[href*="f.general_subject"]::text').getall()
        
        # Tipo de recurso
        tipo_recurso = resource.css('a[href*="f.material_types"]::text').get()
        
        # Licencia
        licencia = resource.css('.cou-bucket span::text').get('')
        
        return {
            'titulo': titulo,
            'descripcion': descripcion.strip(),
            'url_recurso': resource_url,
            'materias': [m.strip() for m in materias if m.strip()],
            'tipo_recurso': tipo_recurso.strip() if tipo_recurso else None,
            'licencia': licencia.strip() if licencia else 'No especificada',
            'timestamp': scrapy.Request._get_time(),
        }