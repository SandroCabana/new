import scrapy
import urllib.parse
from urllib.parse import urljoin, urlencode
from datetime import datetime
import hashlib


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
        'social-science': 'Social Science'
    }
    
    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 100,
        'DOWNLOAD_DELAY': 2,
    }

    def start_requests(self):
        """Generar requests para todas las áreas temáticas"""
        base_url = "https://oercommons.org/courses/"
        
        # Limitar a algunas áreas para prueba
        priority_subjects = ['mathematics', 'physical-science', 'life-science', 'english-language-arts']
        
        for subject_slug in priority_subjects:
            subject_name = self.SUBJECT_AREAS.get(subject_slug, subject_slug)
            params = {
                'batch_size': 20,
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
        
        resources = response.css('article.js-index-item, .search-result-item, .resource-item')
        
        self.logger.info(f"Área: {subject_area} - Recursos encontrados: {len(resources)}")
        
        for resource in resources:
            item = self.extract_resource_data(resource, response)
            if item and item.get('title'):
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
        titulo = resource.css('.item-title a::text, h3 a::text, .title::text').get('').strip()
        if not titulo:
            return None
            
        relative_url = resource.css('.item-title a::attr(href), h3 a::attr(href)').get()
        resource_url = urljoin(response.url, relative_url) if relative_url else response.url
        
        # Generar resource_id único
        resource_id = hashlib.md5(resource_url.encode()).hexdigest()
        
        # Descripción
        descripcion_corta = resource.css('.abstract-short p::text, .description::text').get('')
        descripcion_larga = resource.css('.abstract-full p::text').get('')
        descripcion = descripcion_larga or descripcion_corta or titulo
        
        # Licencia
        licencia_texto = resource.css('.cou-bucket span::text, .license::text').get('')
        licencia_icons = resource.css('.cc::attr(class)').getall()
        licencia = self.parse_license(licencia_texto, licencia_icons)
        
        # Metadatos estructurados
        metadatos = self.extract_metadata(resource)
        
        # Determinar tipo de recurso
        resource_type = self.map_resource_type(metadatos['tipo_recurso'])
        
        # Determinar dificultad
        difficulty = self.map_difficulty(metadatos['nivel_educativo'])
        
        # Combinar tags
        tags = ', '.join(filter(None, [
            ', '.join(metadatos['materias']),
            metadatos['tipo_recurso'],
            licencia
        ]))
        
        return {
            'resource_id': resource_id,
            'title': titulo[:255],
            'description': descripcion[:1000].strip(),
            'url': resource_url[:500],
            'author': metadatos['autor'] or metadatos['proveedor'] or 'OER Commons',
            'resource_type': resource_type,
            'tags': tags[:500],
            'difficulty_level': difficulty,
            'lti_context_id': None,
            'source': 'OER Commons',
            
            # Metadatos adicionales (no se guardan en BD pero útiles para logs)
            'area_tematica': None,  # Se agregará en parse_subject
            'licencia': licencia,
            'fecha_publicacion': metadatos['fecha'],
        }

    def extract_metadata(self, resource):
        """Extraer metadatos estructurados del recurso"""
        
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
                    metadatos['materias'] = dd_element.css('a::text, ::text').getall()
                elif 'material type' in dt_text or 'type' in dt_text:
                    metadatos['tipo_recurso'] = dd_element.css('a::text, ::text').get()
                elif 'level' in dt_text or 'education' in dt_text:
                    metadatos['nivel_educativo'] = dd_element.css('a::text, ::text').getall()
                elif 'provider' in dt_text or 'source' in dt_text:
                    metadatos['proveedor'] = dd_element.css('a::text, ::text').get()
                elif 'author' in dt_text or 'creator' in dt_text:
                    metadatos['autor'] = dd_element.css('::text').get()
                elif 'date' in dt_text:
                    metadatos['fecha'] = dd_element.css('::text').get()
        
        return metadatos

    def parse_license(self, license_text, license_icons):
        """Parsear información de licencia"""
        if license_text and license_text.strip():
            return license_text.strip()
        
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
        
        return "Open License"

    def map_resource_type(self, tipo_oer):
        """Mapear tipo de OER Commons a nuestros tipos"""
        if not tipo_oer:
            return 'other'
        
        tipo_lower = tipo_oer.lower()
        
        if 'video' in tipo_lower or 'multimedia' in tipo_lower:
            return 'video'
        elif 'text' in tipo_lower or 'reading' in tipo_lower or 'book' in tipo_lower:
            return 'article'
        elif 'activity' in tipo_lower or 'interactive' in tipo_lower or 'simulation' in tipo_lower:
            return 'tool'
        elif 'assessment' in tipo_lower or 'quiz' in tipo_lower or 'test' in tipo_lower:
            return 'quiz'
        elif 'lesson' in tipo_lower or 'module' in tipo_lower:
            return 'article'
        else:
            return 'other'

    def map_difficulty(self, niveles):
        """Mapear niveles educativos a dificultad"""
        if not niveles:
            return None
        
        niveles_text = ' '.join(niveles).lower()
        
        if any(word in niveles_text for word in ['college', 'university', 'higher', 'graduate', 'adult']):
            return 'advanced'
        elif any(word in niveles_text for word in ['high school', 'secondary', 'middle']):
            return 'intermediate'
        elif any(word in niveles_text for word in ['elementary', 'primary', 'kindergarten']):
            return 'beginner'
        else:
            return 'intermediate'
