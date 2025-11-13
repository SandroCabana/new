# scraper_project/spiders/test_spider.py
import scrapy

class TestSpider(scrapy.Spider):
    name = 'test_spider'
    start_urls = ['https://www.oercommons.org/browse?batch_size=10']
    
    def parse(self, response):
        self.logger.info("=== TESTING SELECTORS ===")
        
        # Probar selectores
        resources = response.css('article.js-index-item')
        self.logger.info(f"Recursos encontrados: {len(resources)}")
        
        for i, resource in enumerate(resources[:2]):  # Solo primeros 2 para prueba
            self.logger.info(f"\n--- Recurso {i+1} ---")
            
            titulo = resource.css('.item-title a::text').get()
            self.logger.info(f"Título: {titulo}")
            
            descripcion = resource.css('.abstract-short p::text').get()
            self.logger.info(f"Descripción: {descripcion}")
            
            materias = resource.css('a[href*="f.general_subject"]::text').getall()
            self.logger.info(f"Materias: {materias}")