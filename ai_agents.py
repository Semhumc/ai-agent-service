import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from smolagents import CodeAgent, WebSearchTool, tool, OpenAIServerModel
from dotenv import load_dotenv
import requests
import markdownify
import re

# Load environment variables
load_dotenv()

# Logging
logger = logging.getLogger(__name__)

@tool
def visit_webpage(url: str) -> str:
    try:
        logger.info(f"🌐 Web sayfası ziyaret ediliyor: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        markdown_content = markdownify.markdownify(response.text).strip()
        markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)
        
        if len(markdown_content) > 5000:
            markdown_content = markdown_content[:5000] + "\n\n[İçerik kısaltıldı...]"
        
        logger.info(f"✅ Web sayfası başarıyla işlendi. İçerik uzunluğu: {len(markdown_content)}")
        return markdown_content
        
    except Exception as e:
        error_msg = f"Web sayfası erişim hatası: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

class ThemeSpecialistAgent:
    
    def __init__(self, theme_name: str, theme_description: str, specialization: str):
        self.theme_name = theme_name
        self.theme_description = theme_description
        self.specialization = specialization
        
        # API key
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY gerekli!")

        # Model konfigürasyonu
        model = OpenAIServerModel(
            model_id="google/gemini-2.5-flash",
            api_base="https://openrouter.ai/api/v1",
            api_key=api_key,
            max_tokens=4000,
        )

        # Tema-specific system prompt
        system_prompt = self._create_theme_specific_prompt()

        # Agent'ı oluştur
        self.agent = CodeAgent(
            instructions=system_prompt,
            tools=[WebSearchTool(), visit_webpage],
            model=model,
            max_steps=10,
            stream_outputs=True,
            additional_authorized_imports=[
                "time", "numpy", "pandas", "requests", "json", "re", 
                "collections", "statistics", "datetime", "time", 
                "itertools", "stat", "random", "unicodedata", 
                "math", "re", "queue"
            ],
        )
        
        logger.info(f"✅ {self.theme_name} Agent oluşturuldu")

    def _create_theme_specific_prompt(self) -> str:
        """Tema-özel system prompt oluştur"""
        return f"""# {self.theme_name} Kamp Rotası Uzmanı

Sen {self.theme_name} konusunda uzmanlaşmış bir kamp rotası planlama uzmanısın.

## UZMANLIK ALANI: {self.specialization}

## GÖREV:
Sadece {self.theme_name} teması için tek bir rota planı oluşturacaksın. 

## ARAŞTIRMA STRATEJİN:
{self._get_theme_research_strategy()}

## ZORUNLU JSON FORMATII:
```json
{{
  "theme": "{self.theme_name}",
  "description": "{self.theme_description}",
  "trip": {{
    "user_id": "USER_ID_PLACEHOLDER",
    "name": "PLAN_NAME_PLACEHOLDER - {self.theme_name}",
    "description": "DESCRIPTION_PLACEHOLDER",
    "start_position": "START_POSITION_PLACEHOLDER",
    "end_position": "END_POSITION_PLACEHOLDER", 
    "start_date": "START_DATE_PLACEHOLDER",
    "end_date": "END_DATE_PLACEHOLDER",
    "total_days": "TOTAL_DAYS_PLACEHOLDER"
  }},
  "daily_plan": [
    {{
      "day": 1,
      "date": "YYYY-MM-DD",
      "location": {{
        "name": "GERÇEK_KAMP_ALANI_ADI",
        "address": "Detaylı adres bilgisi",
        "site_url": "https://gerçek-website.com",
        "latitude": 37.123456,
        "longitude": 27.654321
      }}
    }}
  ]
}}
```

## KRİTİK KURALLAR:
- SADECE {self.theme_name} temasına uygun kamp alanları araştır
- GERÇEK ve MEVCUT kamp alanları bul
- GPS koordinatları doğru olsun
- Web sitelerini kontrol et
- final_answer() ile JSON döndür

BAŞLA VE {self.theme_name.upper()} ARAŞTIR!"""

    def _get_theme_research_strategy(self) -> str:
        """Tema-özel araştırma stratejisi"""
        strategies = {
            "Doğal Güzellikler Rotası": """
- Milli parklar yakınındaki kamp alanları
- Göl ve deniz kenarı kamp yerleri  
- Orman içi doğal kamp alanları
- Şelale ve doğa yürüyüşü rotaları
- "doğal kamp", "orman kampı", "göl kenarı kamp" anahtar kelimeleri
            """,
            "Tarihi Güzellikler Rotası": """
- Antik kentler yakınındaki kamp alanları
- Müze ve ören yeri çevresi kamp yerleri
- Tarihi şehirler arası rota planlaması
- Kültür rotası kamp alanları
- "tarihi kamp", "antik kent yakını", "kültür rotası" anahtar kelimeleri
            """,
            "Macera ve Aksiyon Rotası": """
- Dağ ve yayla kamp alanları
- Su sporları yapılabilir kamp yerleri
- Trekking ve dağcılık rotaları
- Adrenalin aktiviteli kamp alanları
- "macera kampı", "su sporları kamp", "dağ kampı" anahtar kelimeleri
            """
        }
        return strategies.get(self.theme_name, "Genel araştırma stratejisi")

    def generate_route(self, trip_data: Dict[str, Any]) -> Dict[str, Any]:
        """Bu tema için rota oluştur"""
        try:
            logger.info(f"🎯 {self.theme_name} Agent çalışmaya başladı")
            
            # Prompt oluştur
            user_prompt = f"""
            {self.theme_name} teması için kamp rotası planla:
            
            📋 Bilgiler:
            - Kullanıcı ID: {trip_data['user_id']}
            - Plan Adı: {trip_data['name']}
            - Açıklama: {trip_data['description']}
            - Başlangıç: {trip_data['start_position']}
            - Bitiş: {trip_data['end_position']} 
            - Başlangıç Tarihi: {trip_data['start_date']}
            - Bitiş Tarihi: {trip_data['end_date']}
            - Toplam Gün: {trip_data['total_days']}
            
            {self.theme_name} temasına uygun GERÇEK kamp alanları araştır!
            Sadece JSON formatında döndür!
            """
            
            # Agent çalıştır
            result = self.agent.run(user_prompt)
            
            # JSON'u çıkar ve temizle
            if isinstance(result, dict):
                cleaned_result = result
            elif isinstance(result, str):
                cleaned_result = self._extract_json_from_response(result)
            else:
                raise Exception(f"Beklenmeyen result tipi: {type(result)}")
            
            # Placeholder'ları değiştir
            final_result = self._replace_placeholders(cleaned_result, trip_data)
            
            logger.info(f"✅ {self.theme_name} Agent tamamlandı")
            return final_result
            
        except Exception as e:
            logger.error(f"❌ {self.theme_name} Agent hatası: {str(e)}")
            return self._create_fallback_route(trip_data)

    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Response'tan JSON çıkar"""
        try:
            # JSON extraction patterns
            patterns = [
                r'```(?:json)?\s*(.*?)\s*```',
                r'final_answer\s*\(\s*(["\'])(.*?)\1\s*\)',
                r'final_answer\s*\(\s*(\{.*?\})\s*\)',
                r'(\{.*\})'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response, re.DOTALL)
                for match in matches:
                    try:
                        if isinstance(match, tuple):
                            json_str = match[1] if len(match) > 1 else match[0]
                        else:
                            json_str = match
                            
                        # Temizle
                        json_str = json_str.strip()
                        json_str = re.sub(r',\s*}', '}', json_str)
                        json_str = re.sub(r',\s*]', ']', json_str)
                        
                        parsed = json.loads(json_str)
                        if self._validate_route_structure(parsed):
                            return parsed
                    except:
                        continue
            
            raise Exception("Geçerli JSON bulunamadı")
            
        except Exception as e:
            logger.error(f"❌ JSON extraction hatası: {str(e)}")
            raise

    def _validate_route_structure(self, data: Dict) -> bool:
        """Route yapısını validate et"""
        required_keys = ['theme', 'description', 'trip', 'daily_plan']
        return all(key in data for key in required_keys)

    def _replace_placeholders(self, route_data: Dict, trip_data: Dict) -> Dict:
        """Placeholder'ları gerçek değerlerle değiştir"""
        route_str = json.dumps(route_data)
        
        replacements = {
            'USER_ID_PLACEHOLDER': trip_data['user_id'],
            'PLAN_NAME_PLACEHOLDER': trip_data['name'],
            'DESCRIPTION_PLACEHOLDER': trip_data['description'],
            'START_POSITION_PLACEHOLDER': trip_data['start_position'],
            'END_POSITION_PLACEHOLDER': trip_data['end_position'],
            'START_DATE_PLACEHOLDER': trip_data['start_date'],
            'END_DATE_PLACEHOLDER': trip_data['end_date'],
            'TOTAL_DAYS_PLACEHOLDER': str(trip_data['total_days'])
        }
        
        for placeholder, value in replacements.items():
            route_str = route_str.replace(placeholder, value)
        
        return json.loads(route_str)

    def _create_fallback_route(self, trip_data: Dict) -> Dict:
        """Fallback route oluştur"""
        return {
            "theme": self.theme_name,
            "description": self.theme_description,
            "trip": {
                "user_id": trip_data['user_id'],
                "name": f"{trip_data['name']} - {self.theme_name}",
                "description": trip_data['description'],
                "start_position": trip_data['start_position'],
                "end_position": trip_data['end_position'],
                "start_date": trip_data['start_date'],
                "end_date": trip_data['end_date'],
                "total_days": trip_data['total_days']
            },
            "daily_plan": [{
                "day": 1,
                "date": trip_data['start_date'],
                "location": {
                    "name": f"{self.theme_name.split()[0]} Kamp Alanı",
                    "address": f"{trip_data['start_position']} yakını kamp alanı",
                    "site_url": "",
                    "latitude": 39.0,
                    "longitude": 35.0
                }
            }]
        }

class MainTripPlannerAgent:
    """Ana koordinatör agent"""
    
    def __init__(self):
        # Tema uzmanı agent'ları oluştur
        self.specialists = {
            "doğal": ThemeSpecialistAgent(
                "Doğal Güzellikler Rotası",
                "Göller, şelaleler ve ormanlık alanlar gibi doğal harikaları keşfeden bir rota.",
                "Doğal alanlar, milli parklar, ekolojik kamp alanları"
            ),
            "tarihi": ThemeSpecialistAgent(
                "Tarihi Güzellikler Rotası", 
                "Antik kentler, kaleler ve tarihi yapılar gibi kültürel mirasları barındıran bir rota.",
                "Tarihi mekanlar, antik kentler, kültürel rotalar"
            ),
            "macera": ThemeSpecialistAgent(
                "Macera ve Aksiyon Rotası",
                "Dağcılık, rafting, yamaç paraşütü gibi aktivitelere uygun kamp alanlarını içeren bir rota.",
                "Adrenalin sporları, dağ aktiviteleri, su sporları"
            )
        }
        
        logger.info("✅ Main Trip Planner Agent oluşturuldu")
        logger.info(f"📋 {len(self.specialists)} uzman agent hazır")

    def generate_trip_plan(self, prompt_data: Dict[str, Any]) -> str:
        """Ana koordinasyon fonksiyonu - paralel çalışma"""
        try:
            logger.info("🚀 Main Agent: Görev dağılımı başlıyor...")
            
            # Tarih hesapla
            start_date = datetime.strptime(prompt_data['start_date'], "%Y-%m-%d")
            end_date = datetime.strptime(prompt_data['end_date'], "%Y-%m-%d")
            total_days = (end_date - start_date).days + 1
            
            # Trip data hazırla
            trip_data = {
                **prompt_data,
                'total_days': total_days
            }
            
            # Paralel çalıştırma
            routes = self._run_agents_parallel(trip_data)
            
            # Final response oluştur
            final_response = {
                "trip_options": routes
            }
            
            logger.info(f"✅ Main Agent: {len(routes)} rota başarıyla oluşturuldu")
            return json.dumps(final_response, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Main Agent hatası: {str(e)}")
            return self._create_fallback_response(prompt_data)

    def _run_agents_parallel(self, trip_data: Dict) -> List[Dict]:
        """Agent'ları paralel çalıştır"""
        routes = []
        
        # ThreadPoolExecutor kullanarak paralel çalıştırma
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Her uzman agent'a görev ver
            future_to_agent = {
                executor.submit(agent.generate_route, trip_data): name
                for name, agent in self.specialists.items()
            }
            
            # Sonuçları topla
            for future in as_completed(future_to_agent):
                agent_name = future_to_agent[future]
                try:
                    result = future.result(timeout=120)  # 2 dakika timeout
                    routes.append(result)
                    logger.info(f"✅ {agent_name} agent tamamlandı")
                except Exception as e:
                    logger.error(f"❌ {agent_name} agent hatası: {str(e)}")
                    # Hata durumunda fallback ekle
                    routes.append(self._create_agent_fallback(agent_name, trip_data))
        
        return routes

    def _create_agent_fallback(self, agent_name: str, trip_data: Dict) -> Dict:
        """Belirli bir agent için fallback"""
        theme_map = {
            "doğal": "Doğal Güzellikler Rotası",
            "tarihi": "Tarihi Güzellikler Rotası", 
            "macera": "Macera ve Aksiyon Rotası"
        }
        
        theme_name = theme_map.get(agent_name, "Genel Rota")
        
        return {
            "theme": theme_name,
            "description": f"{theme_name} için plan oluşturulamadı, varsayılan rota.",
            "trip": trip_data,
            "daily_plan": [{
                "day": 1,
                "date": trip_data['start_date'],
                "location": {
                    "name": f"{theme_name.split()[0]} Kamp Alanı",
                    "address": f"{trip_data['start_position']} yakını",
                    "site_url": "",
                    "latitude": 39.0,
                    "longitude": 35.0
                }
            }]
        }

    def _create_fallback_response(self, prompt_data: Dict) -> str:
        """Tam fallback response"""
        try:
            start_date = datetime.strptime(prompt_data['start_date'], "%Y-%m-%d")
            end_date = datetime.strptime(prompt_data['end_date'], "%Y-%m-%d")
            total_days = (end_date - start_date).days + 1
        except:
            total_days = 3
        
        fallback_data = {
            "trip_options": [
                {
                    "theme": "Doğal Güzellikler Rotası",
                    "description": "Varsayılan doğal rota",
                    "trip": {
                        **prompt_data,
                        "total_days": total_days
                    },
                    "daily_plan": [{
                        "day": 1,
                        "date": prompt_data.get('start_date', '2024-01-01'),
                        "location": {
                            "name": "Varsayılan Kamp Alanı",
                            "address": "Varsayılan adres",
                            "site_url": "",
                            "latitude": 39.0,
                            "longitude": 35.0
                        }
                    }]
                }
            ]
        }
        
        return json.dumps(fallback_data, ensure_ascii=False, indent=2)

# Ana AI Agent sınıfını güncelle
class ai_agent:
    def __init__(self):
        """Multi-Agent AI sistemi başlat"""
        self.main_agent = MainTripPlannerAgent()
        logger.info("✅ Multi-Agent AI sistemi başarıyla oluşturuldu")
        
    def generate_trip_plan(self, prompt_data: Dict[str, Any]) -> str:
        """
        Multi-agent sistemle seyahat planı oluştur
        """
        logger.info("🎯 Multi-Agent sistem başlatıldı")
        return self.main_agent.generate_trip_plan(prompt_data)