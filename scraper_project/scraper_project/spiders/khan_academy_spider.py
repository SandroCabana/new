import scrapy
import hashlib
from ..items import EducationalResourceItem


class KhanAcademySpider(scrapy.Spider):
    """
    Spider para extraer recursos de Khan Academy
    """
    name = "khan_academy"
    allowed_domains = ["khanacademy.org"]
    start_urls = [
        "https://www.khanacademy.org/math",
        "https://www.khanacademy.org/science",
        "https://www.khanacademy.org/computing",
    ]
    
    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 30,
        'DOWNLOAD_DELAY': 2,
    }

    def parse(self, response):
        """Parse Khan Academy subject pages"""
        self.logger.info(f"Parsing Khan Academy: {response.url}")
        
        # Extract lesson/video links
        lesson_links = response.css('a[href*="/v/"]::attr(href), a[href*="/e/"]::attr(href)').getall()
        
        for link in lesson_links[:10]:  # Limit per page
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse_lesson)

    def parse_lesson(self, response):
        """Parse individual lesson/video page"""
        try:
            title = response.css('h1::text, title::text').get()
            if not title:
                return
            
            title = title.strip()
            url = response.url
            resource_id = hashlib.md5(url.encode()).hexdigest()
            
            # Extract description
            description = response.css('meta[name="description"]::attr(content)').get() or \
                         response.css('.description::text').get() or ''
            
            # Determine type
            if '/v/' in url:
                resource_type = 'video'
            elif '/e/' in url:
                resource_type = 'tool'  # Interactive exercise
            else:
                resource_type = 'article'
            
            # Extract subject as tag
            subject = response.url.split('/')[3] if len(response.url.split('/')) > 3 else ''
            
            item = EducationalResourceItem(
                resource_id=resource_id,
                title=title[:255],
                description=description[:1000],
                url=url[:500],
                author='Khan Academy',
                resource_type=resource_type,
                tags=subject[:500],
                difficulty_level='beginner',  # Khan Academy is generally beginner-friendly
                lti_context_id=None,
                source='Khan Academy'
            )
            
            self.logger.info(f"Scraped Khan Academy: {title}")
            return item
            
        except Exception as e:
            self.logger.error(f"Error parsing Khan Academy lesson: {e}")
            return None
