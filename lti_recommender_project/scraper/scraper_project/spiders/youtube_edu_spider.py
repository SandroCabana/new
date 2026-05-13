import scrapy
import xml.etree.ElementTree as ET

class YouTubeEduSpider(scrapy.Spider):
    """
    Spider para feeds RSS de canales educativos de YouTube en español.
    Extrae videos recientes para tener recursos multimedia en la BD.
    Sin necesidad de YouTube API (evita quotas limits de GCloud)
    """
    name = "youtube_edu"

    # Diccionario de canales educativos usando IDs (evitando scrape de HTML)
    CHANNELS = {
        "UCy5znSnfMsDwaLlROnZ7Qbg": "DotCSV (IA y Data)",
        "UCbdSYaPD-lr1kW27UJuk8Pw": "QuantumFracture (Física animada)",
        "UCH-Z8ya93m7_RD02WsCSZYA": "Derivando (Matemáticas)",
        "UC55-mxUj5Nj3niXFReG44OQ": "Platzi (Programación/Tech)",
        "UC8LeXCWOalN8SxlrPcG-PaQ": "Midudev (Web Dev/Programación)"
    }

    # YouTube XML namespaces
    NS = {
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
        "atom": "http://www.w3.org/2005/Atom"
    }

    def start_requests(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/atom+xml,application/rss+xml,application/xml;q=0.9,text/xml;q=0.8,*/*;q=0.7"
        }
        for channel_id, channel_name in self.CHANNELS.items():
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            yield scrapy.Request(
                url=url, 
                callback=self.parse_feed, 
                headers=headers,
                cb_kwargs={"channel_name": channel_name}
            )

    def parse_feed(self, response, channel_name):
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            self.logger.error(f"Failed to parse XML for {channel_name}: {e}")
            return

        entries = root.findall("atom:entry", self.NS)
        self.logger.info(f"YouTube EDU - Found {len(entries)} videos for {channel_name}")

        for entry in entries:
            video_id = entry.findtext("yt:videoId", "", self.NS)
            title = entry.findtext("atom:title", "", self.NS).strip()
            
            # YouTube descriptions provide excellent context for our Semantic Search
            group = entry.find("media:group", self.NS)
            description = ""
            if group is not None:
                description = group.findtext("media:description", "", self.NS).strip()
            
            # Use channel name as author
            author = entry.find("atom:author", self.NS)
            author_name = author.findtext("atom:name", channel_name, self.NS) if author is not None else channel_name

            if not video_id or not title:
                continue

            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Tags inferidos (simulados porque RSS no da tags puros)
            infer_tags = []
            lower_title = title.lower()
            if "python" in lower_title or "javascript" in lower_title:
                infer_tags.append("programming")
            if "ia " in lower_title or "ai " in lower_title or "inteligencia artificial" in lower_title:
                infer_tags.append("artificial intelligence")
            if "matemática" in lower_title or "math" in lower_title:
                infer_tags.append("mathematics")
            if "física" in lower_title or "ciencia" in lower_title:
                infer_tags.append("science")

            yield {
                "resource_id": video_url,
                "title": title,
                "description": description[:1500] if description else "Video educativo.",
                "url": video_url,
                "author": author_name,
                "resource_type": "video",
                "tags": ",".join(infer_tags) if infer_tags else "tech,education",
                "difficulty_level": "beginner",  # Videos on YT tend to be more accessible
            }
