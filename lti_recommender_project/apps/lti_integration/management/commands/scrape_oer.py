from django.core.management.base import BaseCommand
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scraper_project.scraper_project.spiders.oer_spider import OerSpider

class Command(BaseCommand):
    help = "Ejecuta el spider de Scrapy para obtener recursos educativos (OER)."

    def handle(self, *args, **options):
        process = CrawlerProcess(get_project_settings())
        process.crawl(OerSpider)
        process.start()
