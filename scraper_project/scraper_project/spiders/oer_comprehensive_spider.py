# scraper_project/spiders/oer_comprehensive_spider.py
import scrapy
import urllib.parse
from urllib.parse import urljoin, urlencode
from datetime import datetime

class OERComprehensiveSpider(scrapy.Spider):
    name = 'oer_comprehensive'
    
    # Todas las áreas temáticas de OER Commons
    SUBJECT_AREAS = {
        'applied-science': 'Applied Science',
        'arts-and-humanities': 'Arts and Humanities', 
        'business-and-communication': 'Business and Communication',
        'career-and-technical-education': 'Career and Technical Education',
        'education': 'Education',
        'english-language-arts': 'English Language Arts',
        'history': 'History',
        'law': 'Law',
        'life-science': 'Life Science',
        'mathematics': 'Mathematics',
        'physical-science': 'Physical Science',
        'research-and-scholarship': 'Research and Scholarship',
        'social-science': 'Social Science'
    }

    def start_requests(self):
        """Generar requests para todas las áreas temáticas"""
        base_url = "https://oercommons.org/courses/"
        
        for subject_slug, subject_name in self.SUBJECT_AREAS.items():
            params = {
                'batch_size': 20,  # Reducido para prueba más rápida
                'sort_by': 'search',
                'view_mode': 'summary',
                'f.general_subject': subject_slug
            }
            
            url = f"{base_url}?{urlencode(params)}"
            
            yield scrapy.Request(
                url,
                callback=self.parse_subject,
                meta={
                    'subject_area': subject_name,
                    'subject_slug': subject_slug
                }
            )

    def parse_subject(self, response):
        """Parsear página de área temática específica"""
        subject_area = response.meta['subject_area']
        subject_slug = response.meta['subject_slug']
        
        resources = response.css('article.js-index-item')
        
        self.logger.info(f"Área: {subject_area} - Recursos encontrados: {len(resources)}")
        
        for resource in resources:
            item = self.extract_resource_data(resource, response)
            if item and item.get('titulo'):
                item['area_tematica_principal'] = subject_area
                item['slug_area_tematica'] = subject_slug
                yield item
        
        # Paginación para el área temática actual
        next_page = response.css('a[rel="next"]::attr(href), .pager-next a::attr(href)').get()
        if next_page:
            next_url = urljoin(response.url, next_page)
            yield scrapy.Request(
                next_url,
                callback=self.parse_subject,
                meta=response.meta
            )

    def extract_resource_data(self, resource, response):
        """Extraer datos detallados de cada recurso"""
        
        # Información básica
        titulo = resource.css('.item-title a::text').get('').strip()
        if not titulo:
            return None
            
        relative_url = resource.css('.item-title a::attr(href)').get()
        resource_url = urljoin(response.url, relative_url) if relative_url else None
        
        # Descripción
        descripcion_corta = resource.css('.abstract-short p::text').get('')
        descripcion_larga = resource.css('.abstract-full p::text').get('')
        descripcion = descripcion_larga or descripcion_corta
        
        # Licencia
        licencia_texto = resource.css('.cou-bucket span::text').get('')
        licencia_icons = resource.css('.cc::attr(class)').getall()
        licencia = self.parse_license(licencia_texto, licencia_icons)
        
        # Metadatos estructurados
        metadatos = self.extract_metadata(resource)
        
        # Rating
        rating_text = resource.css('.stars .sr-only::text').get('')
        rating = self.parse_rating(rating_text)
        
        # Imagen
        imagen = resource.css('img[alt]::attr(src)').get()
        
        return {
            'titulo': titulo,
            'descripcion': descripcion.strip(),
            'url_recurso': resource_url,
            'url_oer': response.url,
            'licencia': licencia,
            'rating': rating,
            'imagen': imagen,
            
            # Metadatos educativos
            'materias': metadatos['materias'],
            'tipo_recurso': metadatos['tipo_recurso'],
            'nivel_educativo': metadatos['nivel_educativo'],
            'proveedor': metadatos['proveedor'],
            'autor': metadatos['autor'],
            'fecha_publicacion': metadatos['fecha'],
            
            # Información técnica - CORREGIDO
            'timestamp_extraccion': datetime.now().isoformat(),  # LÍNEA CORREGIDA
        }

    def extract_metadata(self, resource):
        """Extraer metadatos estructurados del recurso"""
        
        # Inicializar diccionario de metadatos
        metadatos = {
            'materias': [],
            'tipo_recurso': None,
            'nivel_educativo': [],
            'proveedor': None,
            'autor': None,
            'fecha': None
        }
        
        # Extraer información del dl (definition list)
        info_items = resource.css('dt, dd')
        
        for i in range(0, len(info_items), 2):
            if i + 1 < len(info_items):
                dt_text = info_items[i].css('::text').get('').strip().lower().replace(':', '')
                dd_element = info_items[i + 1]
                
                if 'subject' in dt_text:
                    metadatos['materias'] = dd_element.css('a::text').getall()
                elif 'material type' in dt_text:
                    metadatos['tipo_recurso'] = dd_element.css('a::text').get()
                elif 'level' in dt_text:
                    metadatos['nivel_educativo'] = dd_element.css('a::text').getall()
                elif 'provider' in dt_text:
                    metadatos['proveedor'] = dd_element.css('a::text').get()
                elif 'author' in dt_text:
                    metadatos['autor'] = dd_element.css('::text').get()
                elif 'date added' in dt_text:
                    metadatos['fecha'] = dd_element.css('::text').get()
        
        return metadatos

    def parse_license(self, license_text, license_icons):
        """Parsear información de licencia mejorado"""
        if license_text and license_text.strip():
            return license_text.strip()
        
        # Determinar licencia por combinación de iconos
        icons_str = ' '.join(license_icons)
        
        if 'cc-by' in icons_str and 'cc-nc' in icons_str and 'cc-sa' in icons_str:
            return 'CC BY-NC-SA'
        elif 'cc-by' in icons_str and 'cc-nc' in icons_str:
            return 'CC BY-NC'
        elif 'cc-by' in icons_str and 'cc-sa' in icons_str:
            return 'CC BY-SA'
        elif 'cc-by' in icons_str:
            return 'CC BY'
        elif 'cc-zero' in icons_str:
            return 'CC0'
        elif 'cc-publicdomain' in icons_str:
            return 'Public Domain'
        
        return "Licencia no especificada"

    def parse_rating(self, rating_text):
        """Parsear rating del texto"""
        if rating_text:
            import re
            match = re.search(r'(\d+\.?\d*) stars', rating_text)
            if match:
                return float(match.group(1))
        return 0.0