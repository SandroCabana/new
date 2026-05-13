import scrapy
from urllib.parse import urlencode

class OpenAlexEsSpider(scrapy.Spider):
    """
    Spider para la API de OpenAlex (https://openalex.org)
    Extrae works (artículos/papers) en español, de acceso abierto,
    enfocados en Computer Science, Matemáticas y Ciencias Afines.
    """
    name = "openalex_es"

    # Limit to 5 pages (125 results per run) to prevent flooding and keep the DB clean
    MAX_PAGES = 5

    def start_requests(self):
        # Base works API
        base_url = "https://api.openalex.org/works?"
        
        # Filtros:
        # language:es -> Solo en español
        # is_oa:true -> Solo acceso abierto (gratis)
        # has_abstract:true -> Necesitamos resumen para el embedding
        # Utilizar una búsqueda en español y filtros menos estrictos
        params = {
            "search": "educación OR programación OR ciencia OR tecnología OR matemáticas",
            "filter": "language:es,has_oa_accepted_or_published_version:true",
            "per-page": "25",
            "sort": "publication_date:desc",
            "page": 1,
            "mailto": "admin@example.com"
        }
        
        url = base_url + urlencode(params)
        yield scrapy.Request(
            url=url, 
            callback=self.parse,
            headers={"Accept-Encoding": "gzip, deflate"},
            cb_kwargs={'page': 1, 'base_url': base_url, 'params': params}
        )

    def parse(self, response, page, base_url, params):
        try:
            # Scrapy middleware should handle gzip, but sometimes OpenAlex raw bytes bypass it.
            if response.body.startswith(b'\x1f\x8b'):
                import gzip
                data = json.loads(gzip.decompress(response.body).decode('utf-8'))
            else:
                data = response.json()
        except Exception as e:
            self.logger.error(f"Failed to decode JSON: {e} - Body sample: {response.body[:100]}")
            return
            
        results = data.get("results", [])
        
        self.logger.info(f"OpenAlex ES - Page {page}: Found {len(results)} works.")
        
        if not results:
            return

        for work in results:
            title = work.get("title")
            if not title:
                continue

            # Obtenemos la URL de acceso abierto principal
            open_access = work.get("open_access", {})
            url = open_access.get("oa_url")
            if not url:
                url = work.get("id") # Fallback to OpenAlex URL

            # Obtener el abstract (en OpenAlex viene en formato indexado invertido)
            abstract_inverted = work.get("abstract_inverted_index", {})
            abstract = self._reconstruct_abstract(abstract_inverted)
            
            # Autores
            authors = []
            for authorship in work.get("authorships", []):
                author_name = authorship.get("author", {}).get("display_name")
                if author_name:
                    authors.append(author_name)
                    
            # Conceptos (Tags)
            tags = []
            for concept in work.get("concepts", []):
                tags.append(concept.get("display_name"))

            # Save structure based on apps/resources/models.py
            yield {
                "resource_id": work.get("id"),
                "title": title.strip(),
                "description": abstract[:1500] if abstract else "Abstract no disponible",
                "url": url,
                "author": ", ".join(authors[:3]) if authors else "Desconocido",
                "resource_type": "article",
                "tags": ",".join(tags[:5]) if tags else "",
                "difficulty_level": "advanced",
            }
            
        # Paginación
        if page < self.MAX_PAGES:
            next_page = page + 1
            params["page"] = next_page
            next_url = base_url + urlencode(params)
            yield scrapy.Request(
                url=next_url,
                callback=self.parse,
                cb_kwargs={'page': next_page, 'base_url': base_url, 'params': params}
            )

    def _reconstruct_abstract(self, inverted_index):
        """Reconstruye el texto real a partir del índice invertido de OpenAlex"""
        if not inverted_index:
            return ""
            
        # El invertido es: {"word": [position1, position2]}
        # Aislaremos todos los pares (posición, palabra)
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
                
        # Ordenar por posición y unir
        word_positions.sort(key=lambda x: x[0])
        return " ".join(word for pos, word in word_positions)
