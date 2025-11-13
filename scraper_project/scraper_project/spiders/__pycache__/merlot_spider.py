import scrapy
import xml.etree.ElementTree as ET
from recommender_app.models import EducationalResource

class MerlotSpider(scrapy.Spider):
    name = "merlot"
    allowed_domains = ["merlot.org"]

    def start_requests(self):
        keywords = ["mathematics", "physics", "history"]
        for kw in keywords:
            url = f"https://www.merlot.org/merlot/materials.rest?keywords={kw}"
            yield scrapy.Request(url=url, callback=self.parse, cb_kwargs={"keyword": kw})

    def parse(self, response, keyword):
        root = ET.fromstring(response.text)
        for material in root.findall(".//material"):
            item = {
                "resource_id": material.findtext("id"),
                "title": material.findtext("title"),
                "description": material.findtext("description"),
                "url": material.findtext("url"),
                "author": material.findtext("author"),
                "resource_type": material.findtext("type") or "other",
                "tags": keyword,
            }

            # Guardar en la BD Django
            EducationalResource.objects.update_or_create(
                resource_id=item["resource_id"],
                defaults=item
            )

            yield item
