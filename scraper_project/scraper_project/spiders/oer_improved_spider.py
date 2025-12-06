import scrapy
import hashlib
from urllib.parse import urljoin
from ..items import EducationalResourceItem


class ImprovedOerSpider(scrapy.Spider):
    """
    Spider mejorado para OER Commons con manejo de errores robusto
    """
    name = "oer_improved"
    allowed_domains = ["oercommons.org"]
    start_urls = ["https://www.oercommons.org/courses"]
    
    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 50,  # Límite de recursos a extraer
        'DOWNLOAD_DELAY': 2,  # Ser respetuosos con el servidor
    }

    def parse(self, response):
        """Parse the main listing page"""
        self.logger.info(f"Parsing: {response.url}")
        
        # Intentar diferentes selectores para adaptarse a cambios en el sitio
        resource_selectors = [
            '.search-result-item',
            '.resource-card',
            'article.resource',
            '.oer-item'
        ]
        
        resources_found = False
        for selector in resource_selectors:
            resources = response.css(selector)
            if resources:
                self.logger.info(f"Found {len(resources)} resources using selector: {selector}")
                resources_found = True
                for resource in resources:
                    yield self.parse_resource(resource, response)
                break
        
        if not resources_found:
            self.logger.warning(f"No resources found on {response.url}")
            # Log HTML for debugging
            self.logger.debug(f"Page HTML snippet: {response.text[:500]}")
        
        # Pagination
        next_page = response.css('a.next::attr(href)').get() or \
                   response.css('a[rel="next"]::attr(href)').get() or \
                   response.css('.pagination a:contains("Next")::attr(href)').get()
        
        if next_page:
            yield response.follow(next_page, self.parse)

    def parse_resource(self, resource, response):
        """Extract data from a single resource"""
        try:
            # Extract title
            title = (resource.css('h3::text').get() or 
                    resource.css('.title::text').get() or
                    resource.css('a::text').get() or
                    'Sin título').strip()
            
            # Extract URL
            url = (resource.css('a::attr(href)').get() or
                  resource.css('::attr(href)').get())
            if url:
                url = response.urljoin(url)
            else:
                self.logger.warning(f"No URL found for resource: {title}")
                return None
            
            # Generate unique resource_id
            resource_id = hashlib.md5(url.encode()).hexdigest()
            
            # Extract description
            description = (resource.css('.description::text').get() or
                          resource.css('p::text').get() or
                          resource.css('.summary::text').get() or
                          '').strip()
            
            # Extract author
            author = (resource.css('.author::text').get() or
                     resource.css('.creator::text').get() or
                     '').strip()
            
            # Extract tags
            tags = resource.css('.tag::text, .subject::text').getall()
            tags_str = ', '.join([tag.strip() for tag in tags if tag.strip()])
            
            # Determine resource type
            resource_type = self.determine_type(title, description, url)
            
            # Create item
            item = EducationalResourceItem(
                resource_id=resource_id,
                title=title[:255],  # Limit to field max_length
                description=description[:1000] if description else '',
                url=url[:500],
                author=author[:255] if author else '',
                resource_type=resource_type,
                tags=tags_str[:500] if tags_str else '',
                difficulty_level=None,
                lti_context_id=None,
                source='OER Commons'
            )
            
            self.logger.info(f"Scraped: {title}")
            return item
            
        except Exception as e:
            self.logger.error(f"Error parsing resource: {e}")
            return None

    def determine_type(self, title, description, url):
        """Determine resource type based on content"""
        text = f"{title} {description} {url}".lower()
        
        if any(word in text for word in ['video', 'youtube', 'vimeo', 'watch']):
            return 'video'
        elif any(word in text for word in ['pdf', '.pdf']):
            return 'pdf'
        elif any(word in text for word in ['quiz', 'test', 'assessment', 'exam']):
            return 'quiz'
        elif any(word in text for word in ['interactive', 'simulation', 'game']):
            return 'tool'
        elif any(word in text for word in ['article', 'lesson', 'tutorial']):
            return 'article'
        else:
            return 'other'
