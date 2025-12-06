import scrapy

class OerSpider(scrapy.Spider):
    name = "oer"
    start_urls = ["https://www.oercommons.org/browse"]

    def parse(self, response):
        for resource in response.css(".oer-resource-card"):
            yield {
                "resource_id": response.urljoin(resource.css("a::attr(href)").get()),
                "title": resource.css("h3::text").get(),
                "description": resource.css(".description::text").get(),
                "url": response.urljoin(resource.css("a::attr(href)").get()),
                "author": resource.css(".author::text").get(),
                "resource_type": "article",  # se puede mejorar con reglas según el sitio
                "tags": ",".join(resource.css(".tags span::text").getall()),
                "difficulty_level": None,  # si no existe, lo dejamos vacío
            }

        # paginación
        next_page = response.css("a.next::attr(href)").get()
        if next_page:
            yield response.follow(next_page, self.parse)
