import re
import json
import logging
import markdownify
import requests
from typing import Dict, Any
from smolagents import CodeAgent, WebSearchTool, tool, OpenAIServerModel

# Logging
logger = logging.getLogger(__name__)

@tool
def visit_webpage(url: str) -> str:
    """
    Web sayfasını ziyaret eder ve içeriği markdown formatında döndürür
    
    Args:
        url (str): Ziyaret edilecek URL
        
    Returns:
        str: Web sayfasının markdown formatındaki içeriği
    """
    try:
        logger.info(f"🌐 Web sayfası ziyaret ediliyor: {url}")
        
        # HTTP headers ekle (bot detection'ı engellemek için)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # GET request gönder
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # HTML'i Markdown'a çevir
        markdown_content = markdownify.markdownify(response.text).strip()
        
        # Çok fazla boş satırı temizle
        markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)
        
        # İçerik uzunluğunu sınırla (token limiti için)
        if len(markdown_content) > 5000:
            markdown_content = markdown_content[:5000] + "\n\n[İçerik kısaltıldı...]"
        
        logger.info(f"✅ Web sayfası başarıyla işlendi. İçerik uzunluğu: {len(markdown_content)}")
        return markdown_content
        
    except requests.RequestException as e:
        error_msg = f"Web sayfası erişim hatası: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg
    except Exception as e:
        error_msg = f"Beklenmeyen hata: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

class ai_agent:
    def __init__(self):
        """AI Agent'ı başlat"""
        try:
            # System prompt'u yükle
            with open("system_prompt.txt", "r", encoding="utf-8") as file:
                system_prompt = file.read()
            logger.info("✅ System prompt yüklendi")
        except FileNotFoundError:
            logger.warning("⚠️ System prompt dosyası bulunamadı. Default prompt kullanılıyor.")
            system_prompt = "You are a helpful AI assistant for trip planning."

        # Model konfigürasyonu
        model = OpenAIServerModel(
            model_id="google/gemini-2.5-flash",
            api_base="https://openrouter.ai/api/v1",
            api_key="",  # Buraya API key'inizi ekleyin
            max_tokens=8000,
        )

        # Agent'ı oluştur
        self.agent = CodeAgent(
            instructions=system_prompt,
            tools=[WebSearchTool(), visit_webpage],  # self.visit_webpage yerine visit_webpage
            model=model,
            stream_outputs=True,
            additional_authorized_imports=["time", "numpy", "pandas", "requests", "json", "re", "collections", "statistics", "datetime", "time", "itertools", "stat", "random", "unicodedata", "math", "re", "queue"],
        )
        logger.info("✅ AI Agent başarıyla oluşturuldu")
    def generate_trip_plan(self, prompt_data: Dict[str, Any]) -> str:
        """
        Verilen bilgilere dayanarak bir seyahat planı oluşturur
        
        Args:
            prompt_data (dict): Seyahat planı için gerekli bilgiler
            
        Returns:
            str: JSON formatında seyahat planı
        """
        try:
            logger.info(f"🎯 Seyahat planı oluşturuluyor: {prompt_data}")
            
            # User prompt oluştur
            user_prompt = f"""
            Lütfen aşağıdaki bilgilere göre bir seyahat planı oluştur ve sadece belirtilen JSON formatında yanıt ver:
            
            📋 Bilgiler:
            - Kullanıcı ID: {prompt_data['user_id']}
            - Plan Adı: {prompt_data['name']}
            - Açıklama: {prompt_data['description']}
            - Başlangıç Noktası: {prompt_data['start_position']}
            - Bitiş Noktası: {prompt_data['end_position']}
            - Başlangıç Tarihi: {prompt_data['start_date']}
            - Bitiş Tarihi: {prompt_data['end_date']}
            
            ⚠️ ÖNEMLİ: Sadece JSON formatında yanıt ver, başka açıklama ekleme!
            """
            
            logger.info("🤖 AI Agent çalıştırılıyor...")
            
            # Agent'ı çalıştır
            result_str = self.agent.run(user_prompt)
            
            logger.info(f"🧠 AI'dan gelen ham sonuç uzunluğu: {len(result_str)} karakter")
            logger.debug(f"Ham sonuç: {result_str[:500]}...")  # İlk 500 karakteri log'la
            
            # JSON formatını temizle
            cleaned_result = self._clean_json_response(result_str)
            
            # JSON validasyonu
            try:
                json.loads(cleaned_result)
                logger.info("✅ JSON formatı geçerli")
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON format hatası: {str(e)}")
                # Fallback JSON oluştur
                cleaned_result = self._create_fallback_json(prompt_data)
                
            return cleaned_result
            
        except Exception as e:
            logger.error(f"❌ Seyahat planı oluşturma hatası: {str(e)}")
            # Fallback JSON döndür
            return self._create_fallback_json(prompt_data)

    def _clean_json_response(self, response: str) -> str:
        """JSON yanıtını temizle ve düzenle"""
        try:
            # Kod bloklarını temizle
            if "```json" in response:
                response = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if response:
                    response = response.group(1)
                else:
                    response = response.strip()
            
            # Başındaki ve sonundaki gereksiz karakterleri temizle
            response = response.strip()
            
            # JSON dışındaki açıklamaları temizle
            lines = response.split('\n')
            json_lines = []
            in_json = False
            
            for line in lines:
                if line.strip().startswith('{') or in_json:
                    in_json = True
                    json_lines.append(line)
                    if line.strip().endswith('}') and json_lines:
                        break
            
            if json_lines:
                response = '\n'.join(json_lines)
            
            # Property isimlerini düzelt (quote'lar eksikse)
            response = re.sub(r'(\w+):', r'"\1":', response)
            response = re.sub(r'""(\w+)":', r'"\1":', response)  # Çift quote'u düzelt
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"❌ JSON temizleme hatası: {str(e)}")
            return response

    def _create_fallback_json(self, prompt_data: Dict[str, Any]) -> str:
        """Hata durumunda fallback JSON oluştur"""
        fallback_data = {
            "trip": {
                "user_id": prompt_data['user_id'],
                "name": prompt_data['name'],
                "description": prompt_data['description'],
                "start_position": prompt_data['start_position'],
                "end_position": prompt_data['end_position'],
                "start_date": prompt_data['start_date'],
                "end_date": prompt_data['end_date'],
                "total_days": 3,
                "route_summary": "Güzel bir kamp rotası planlandı."
            },
            "daily_plan": [
                {
                    "day": 1,
                    "date": prompt_data['start_date'],
                    "location": {
                        "name": f"{prompt_data['start_position']} Kamp Alanı",
                        "address": f"{prompt_data['start_position']} yakını",
                        "site_url": "",
                        "latitude": 39.0,
                        "longitude": 35.0,
                        "notes": "Güzel doğal kamp alanı"
                    }
                },
                {
                    "day": 2,
                    "date": prompt_data['end_date'],
                    "location": {
                        "name": f"{prompt_data['end_position']} Kamp Alanı",
                        "address": f"{prompt_data['end_position']} yakını",
                        "site_url": "",
                        "latitude": 38.0,
                        "longitude": 36.0,
                        "notes": "Son gün kamp alanı"
                    }
                }
            ]
        }
        
        logger.info("🔧 Fallback JSON oluşturuldu")
        return json.dumps(fallback_data, ensure_ascii=False, indent=2)