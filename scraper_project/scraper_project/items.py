# Define here the models for your scraped items
import scrapy


class EducationalResourceItem(scrapy.Item):
    """Item for scraped educational resources"""
    resource_id = scrapy.Field()
    title = scrapy.Field()
    description = scrapy.Field()
    url = scrapy.Field()
    author = scrapy.Field()
    resource_type = scrapy.Field()
    tags = scrapy.Field()
    difficulty_level = scrapy.Field()
    lti_context_id = scrapy.Field()
    source = scrapy.Field()  # Where the resource was scraped from
