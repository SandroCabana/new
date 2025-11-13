# scraper_project/pipelines.py
import re
from datetime import datetime

class OEREducationalPipeline:
    """Pipeline para procesar recursos educativos de OER Commons"""
    
    def process_item(self, item, spider):
        try:
            # Validar datos mínimos
            if not self.es_recurso_valido(item):
                return None
                
            # Limpieza y normalización
            item = self.limpiar_datos(item)
            
            # Enriquecer con metadatos educativos
            item = self.enriquecer_metadatos_educativos(item)
            
            # Categorizar automáticamente
            item = self.categorizar_automaticamente(item)
            
            # Calcular calidad del recurso
            item = self.calcular_calidad_recurso(item)
            
            return item
            
        except Exception as e:
            spider.logger.error(f"Error en pipeline: {e}")
            return None

    def es_recurso_valido(self, item):
        """Validar si es un recurso educativo válido"""
        return (
            item.get('titulo') and 
            len(item.get('titulo', '')) > 5 and
            item.get('descripcion') and 
            len(item.get('descripcion', '')) > 20
        )

    def limpiar_datos(self, item):
        """Limpieza completa de datos"""
        for key, value in item.items():
            if isinstance(value, str):
                item[key] = self.limpiar_texto(value)
            elif isinstance(value, list):
                item[key] = [self.limpiar_texto(v) for v in value if v and isinstance(v, str)]
        
        return item

    def limpiar_texto(self, texto):
        """Limpieza avanzada de texto"""
        if not texto:
            return ""
        texto = re.sub(r'\s+', ' ', texto)
        return texto.strip()

    def enriquecer_metadatos_educativos(self, item):
        """Enriquecer con metadatos educativos adicionales"""
        descripcion = item.get('descripcion', '').lower()
        titulo = item.get('titulo', '').lower()
        
        item['nivel_dificultad'] = self.estimar_dificultad(descripcion, titulo)
        item['procesado_en'] = datetime.now().isoformat()
        
        return item

    def categorizar_automaticamente(self, item):
        """Categorización automática basada en contenido"""
        descripcion = item.get('descripcion', '').lower()
        titulo = item.get('titulo', '').lower()
        
        categorias_palabras_clave = {
            'matematicas': ['math', 'algebra', 'calculus', 'geometry'],
            'ciencias': ['science', 'biology', 'chemistry', 'physics'],
            'programacion': ['programming', 'coding', 'computer'],
            'economia': ['economics', 'economic', 'market', 'profit'],
            'humanidades': ['history', 'literature', 'philosophy', 'art']
        }
        
        categorias_detectadas = []
        texto_completo = f"{titulo} {descripcion}"
        
        for categoria, palabras in categorias_palabras_clave.items():
            if any(palabra in texto_completo for palabra in palabras):
                categorias_detectadas.append(categoria)
        
        item['categorias_detectadas'] = list(set(categorias_detectadas))
        return item

    def calcular_calidad_recurso(self, item):
        """Calcular score de calidad del recurso"""
        score = 0
        if item.get('titulo'): score += 1
        if item.get('descripcion') and len(item.get('descripcion', '')) > 100: score += 2
        if item.get('licencia') and 'CC' in item.get('licencia', ''): score += 2
        
        item['score_calidad'] = min(score, 10)
        return item

    def estimar_dificultad(self, descripcion, titulo):
        """Estimar nivel de dificultad"""
        texto = f"{titulo} {descripcion}".lower()
        if any(word in texto for word in ['advanced', 'expert', 'complex']):
            return 'Avanzado'
        elif any(word in texto for word in ['intermediate', 'undergraduate']):
            return 'Intermedio'
        return 'Basico'

# Mantener compatibilidad con el nombre anterior
OERProcessingPipeline = OEREducationalPipeline