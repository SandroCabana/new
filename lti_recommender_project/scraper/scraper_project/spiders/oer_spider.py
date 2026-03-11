import scrapy
import xml.etree.ElementTree as ET
from urllib.parse import quote

class OerSpider(scrapy.Spider):
    """
    Spider que obtiene recursos educativos de la API de arXiv.
    arXiv es gratuito, sin autenticación, y devuelve contenido académico real.
    Cubre CS, ML, Física, Matemáticas — ideal para un recomendador educativo.
    """
    name = "oer"

    # Categorías de arXiv relevantes para educación en tecnología
    CATEGORIES = [
        "cs.AI",   # Inteligencia Artificial
        "cs.LG",   # Machine Learning
        "cs.CV",   # Computer Vision
        "cs.CL",   # Computation and Language (NLP)
        "cs.SE",   # Software Engineering
    ]

    NS = {"atom": "http://www.w3.org/2005/Atom"}

    def start_requests(self):
        for cat in self.CATEGORIES:
            url = (
                f"http://export.arxiv.org/api/query"
                f"?search_query=cat:{cat}"
                f"&sortBy=submittedDate&sortOrder=descending"
                f"&max_results=50"
            )
            yield scrapy.Request(url=url, callback=self.parse_atom, cb_kwargs={"category": cat})

    def parse_atom(self, response, category):
        root = ET.fromstring(response.text)
        entries = root.findall("atom:entry", self.NS)
        self.logger.info(f"Got {len(entries)} entries for category {category}")

        for entry in entries:
            title = entry.findtext("atom:title", "", self.NS).strip()
            summary = entry.findtext("atom:summary", "", self.NS).strip()
            url = entry.findtext("atom:id", "", self.NS).strip()
            authors = [
                a.findtext("atom:name", "", self.NS)
                for a in entry.findall("atom:author", self.NS)
            ]
            tags = [
                t.get("term", "")
                for t in entry.findall("atom:category", self.NS)
                if t.get("scheme", "").endswith("arxiv")
            ]

            if not title or not url:
                continue

            yield {
                "resource_id": url,
                "title": title,
                "description": summary[:1000],
                "url": url,
                "author": ", ".join(authors[:3]),
                "resource_type": "article",
                "tags": ",".join(tags[:5]),
                "difficulty_level": "advanced",
            }

