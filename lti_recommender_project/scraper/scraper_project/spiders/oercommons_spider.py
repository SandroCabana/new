import scrapy

class OerCommonsSpider(scrapy.Spider):
    name = "oercommons"
    start_urls = ["https://www.oercommons.org/browse"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={"playwright": True},  # Renderizar con navegador
            )

    async def parse(self, response):
        # ahora sí deberías ver títulos
        titles = response.css("h2::text").getall()
        for t in titles:
            yield {"title": t.strip()}
