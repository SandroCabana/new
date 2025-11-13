# scraper_project/spiders/oer_commons_corrected.py
import scrapy
import re
from urllib.parse import urljoin

class OERCommonsCorrectedSpider(scrapy.Spider):
    name = 'oer_commons_corrected'
    
    start_urls = [
        'https://www.oercommons.org/browse?f.keyword=economics',
        'https://www.oercommons.org/browse?f.keyword=mathematics', 
        'https://www.oercommons.org/browse?f.keyword=science',
        'https://www.oercommons.org/browse?f.keyword=programming'
    ]
    
    custom_settings = {
        'FEED_FORMAT': 'json',
        'FEED_URI': 'oer_corrected_%(time)s.json',
        'ROBOTSTXT_OBEY': True,
        'DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS': 4,
    }

    def parse(self, response):
        """Parsear la página de listado de recursos"""
        
        # Extraer todos los artículos de recursos
        resources = response.css('article.js-index-item')
        
        self.logger.info(f"Encontrados {len(resources)} recursos en {response.url}")
        
        for resource in resources:
            item = self.extract_resource_data(resource, response)
            if item and item.get('titulo'):  # Solo procesar si tiene título
                yield item
        
        # Paginación - buscar el enlace "Next"
        next_page = response.css('a[rel="next"]::attr(href), .pager-next a::attr(href)').get()
        if next_page:
            next_url = urljoin(response.url, next_page)
            yield scrapy.Request(next_url, callback=self.parse)

    def extract_resource_data(self, resource, response):
        """Extraer datos de un recurso individual desde el listado"""
        
        # Título - CORREGIDO
        titulo = resource.css('.item-title a::text').get()
        
        # URL del recurso - CORREGIDO
        relative_url = resource.css('.item-title a::attr(href)').get()
        resource_url = urljoin(response.url, relative_url) if relative_url else None
        
        # Descripción - CORREGIDO
        descripcion_corta = resource.css('.abstract-short p::text').get()
        descripcion_larga = resource.css('.abstract-full p::text').get()
        descripcion = descripcion_larga or descripcion_corta or ""
        
        # Licencia - CORREGIDO
        licencia_texto = resource.css('.cou-bucket span::text').get()
        licencia_icons = resource.css('.cc::attr(class)').getall()
        licencia = self.parse_license(licencia_texto, licencia_icons)
        
        # Materias - CORREGIDO
        materias = resource.css('a[href*="f.general_subject"]::text').getall()
        
        # Tipo de recurso - CORREGIDO
        tipo_recurso = resource.css('a[href*="f.material_types"]::text').get()
        
        # Autor - CORREGIDO (buscar en el texto del dd después de "Author:")
        autor = None
        info_items = resource.css('dt, dd').getall()
        for i, item in enumerate(info_items):
            if 'Author:' in item:
                if i + 1 < len(info_items):
                    autor_match = re.search(r'<dd>(.*?)</dd>', info_items[i + 1])
                    if autor_match:
                        autor = autor_match.group(1)
                        break
        
        # Si no encontramos autor de esa manera, intentamos otra
        if not autor:
            autor = resource.css('dd:contains("Sal")::text').get()
        
        # Proveedor - CORREGIDO
        proveedor = resource.css('a[href*="f.provider"]::text').get()
        
        # Fecha - CORREGIDO
        fecha = resource.css('dd:contains("/202")::text').get()
        
        # Rating - CORREGIDO
        rating_text = resource.css('.stars .sr-only::text').get()
        rating = self.parse_rating(rating_text)
        
        # Imagen
        imagen = resource.css('img[alt]::attr(src)').get()
        
        return {
            'titulo': titulo.strip() if titulo else None,
            'descripcion': descripcion.strip() if descripcion else "",
            'autor': autor.strip() if autor else None,
            'materias': [m.strip() for m in materias if m.strip()],
            'tipo_recurso': tipo_recurso.strip() if tipo_recurso else "Lesson",
            'licencia': licencia,
            'proveedor': proveedor.strip() if proveedor else None,
            'fecha_publicacion': fecha.strip() if fecha else None,
            'rating': rating,
            'url_recurso': resource_url,
            'imagen': imagen,
            'url_oer': response.url,
            'timestamp_extraccion': scrapy.Request._get_time(),
        }

    def parse_license(self, license_text, license_icons):
        """Parsear información de licencia"""
        if license_text:
            return license_text.strip()
        
        # Intentar determinar licencia por iconos
        if license_icons:
            icons_str = ' '.join(license_icons)
            if 'cc-by' in icons_str and 'cc-nc' in icons_str:
                return 'CC BY-NC'
            elif 'cc-by' in icons_str:
                return 'CC BY'
            elif 'cc-by-sa' in icons_str:
                return 'CC BY-SA'
        
        return "Licencia no especificada"

    def parse_rating(self, rating_text):
        """Parsear rating del texto"""
        if rating_text:
            match = re.search(r'(\d+\.?\d*) stars', rating_text)
            if match:
                return float(match.group(1))
        return 0.0