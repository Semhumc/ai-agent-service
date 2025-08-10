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
    """
    Belirtilen URL'deki web sayfasını ziyaret eder ve içeriğini markdown formatında döndürür.
    
    Args:
        url (str): Ziyaret edilecek web sayfasının URL'i
        
    Returns:
        str: Web sayfasının markdown formatındaki içeriği
    """
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
    """Alt Agent - Sadece bilgi toplama ve araştırma yapar, JSON formatlamaz"""
    
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

        # Tema-specific system prompt - SADECE BİLGİ TOPLAMA
        system_prompt = self._create_research_prompt()

        # Agent'ı oluştur
        self.agent = CodeAgent(
            instructions=system_prompt,
            tools=[WebSearchTool(), visit_webpage],
            model=model,
            max_steps=10,  # Daha az step, daha odaklı araştırma
            stream_outputs=True,
            additional_authorized_imports=[
                "time", "numpy", "pandas", "requests", "json", "re", 
                "collections", "statistics", "datetime", "time", 
                "itertools", "stat", "random", "unicodedata", 
                "math", "re", "queue"
            ],
        )
        
        logger.info(f"✅ {self.theme_name} Research Agent oluşturuldu")

    def _create_research_prompt(self) -> str:
        """Sadece araştırma odaklı prompt - JSON formatlamaz"""
        return f"""# {self.theme_name} Kamp Rotası Araştırma Uzmanı

Sen {self.theme_name} konusunda uzmanlaşmış bir araştırma uzmanısın.

## UZMANLIK ALANI: {self.specialization}

## GÖREV:
Sadece {self.theme_name} teması için kamp alanları ARAŞTIR ve BİLGİ TOPLA. 
JSON formatlamaya ÇALIŞMA - sadece bilgi döndür!

## ARAŞTIRMA STRATEJİN:
{self._get_theme_research_strategy()}

## ÇOK ÖNEMLİ:
- JSON formatında çıktı verme
- final_answer() kullanma
- Sadece bulduğun kamp alanlarının bilgilerini döndür
- Her kamp alanı için: İsim, Adres, Web sitesi, GPS koordinatları

## ARAMA YÖNTEMİ:
1. Genel {{şehir}} camping karavan park ara
2. "{{şehir}} çadır kamp" veya "{{şehir}}tatil köyü" ara
3. "{{şehir}} kamp yeri" veya "{{şehir}} pansiyon kamp" ara
4. Bulunan yerleri tek tek araştır
5. Koordinat için "{{yer_adı}} adres konum" ara

## ÇIKTI FORMATI:
Basit metin formatında döndür:

KAMP YERİ 1:
- İsim: [Gerçek camping/karavan park adı]
- Adres: [Tam adres]
- Web sitesi: [URL]
- Latitude: [koordinat]
- Longitude: [koordinat]
- Notlar: [Özel özellikler, aktiviteler]

KAMP YERİ 2:
- İsim: [Gerçek camping/karavan park adı]
...

ARAŞTIR VE BİLGİ TOPLA! Türkiye'de yaygın terimler:
- Camping (en yaygın)
- Karavan Park  
- Tatil Köyü (kamp imkanı olan)
- Pansiyon Kamp
- Çadır Kamp Yeri
- Kamp ve Karavan Parkı"""

    def _get_theme_research_strategy(self) -> str:
        """Tema-özel araştırma stratejisi"""
        strategies = {
            "Doğal Güzellikler Rotası": """
ARAŞTIRMA KELİMELERİ:
- "{şehir} camping karavan park"
- "{şehir} çadır kamp yeri"
- "{şehir} orman kampı"
- "{şehir} göl kenarı camping"
- "{lokasyon} milli park yakını kamp"
- "doğa kampı {bölge}"

ARANACAK ÖZELLIKLER:
- Orman içi lokasyonlar
- Göl/deniz kenarı
- Milli park yakını
- Doğa yürüyüşü rotaları
            """,
            "Tarihi Güzellikler Rotası": """
ARAŞTIRMA KELİMELERİ:
- "{şehir} camping tarihi yerlere yakın"
- "{antik_kent} yakını pansiyon kamp"
- "{müze} çevresinde camping"
- "kültür rotası {bölge} kamp"
- "{tarihi_yer} camping karavan"
- "{şehir} tatil köyü tarihi"

ARANACAK ÖZELLIKLER:
- Antik kentler yakını
- Müze çevresinde
- Tarihi şehir merkezlerine yakın
- Kültür rotası üzerinde
            """,
            "Macera ve Aksiyon Rotası": """
ARAŞTIRMA KELİMELERİ:
- "{şehir} dağ evi camping"
- "{lokasyon} yayla kamp yeri"
- "{bölge} su sporları camping"
- "yayla kampı {dağ}"
- "rafting {nehir} kamp"
- "{şehir} macera turizm kamp"

ARANACAK ÖZELLIKLER:
- Dağlık alan kampları
- Su sporları imkanı
- Trekking rotaları yakını
- Adrenalin sporları
            """
        }
        return strategies.get(self.theme_name, "Genel araştırma stratejisi")

    def research_camps(self, trip_data: Dict[str, Any]) -> str:
        """Bu tema için kamp alanlarını araştır - SADECE BİLGİ DÖNDÜR"""
        try:
            logger.info(f"🎯 {self.theme_name} Research Agent çalışmaya başladı")
            
            # Prompt oluştur
            user_prompt = f"""
            {self.theme_name} teması için kamp yerleri araştır:
            
            📋 Rota Bilgileri:
            - Başlangıç: {trip_data['start_position']}
            - Bitiş: {trip_data['end_position']} 
            - Başlangıç Tarihi: {trip_data['start_date']}
            - Bitiş Tarihi: {trip_data['end_date']}
            - Toplam Gün: {trip_data['total_days']}
            
            Türkiye'de GERÇEK camping, karavan parkı, tatil köyü, pansiyon kamp bul!
            "kamp alanı" yerine "camping", "karavan park", "kamp yeri" terimlerini kullan!
            JSON formatlamaya çalışma - sadece bilgi döndür!
            """
            
            # Agent çalıştır
            result = self.agent.run(user_prompt)
            
            logger.info(f"✅ {self.theme_name} Research Agent tamamlandı")
            return str(result) if result else f"{self.theme_name} için araştırma tamamlanamadı."
            
        except Exception as e:
            logger.error(f"❌ {self.theme_name} Research Agent hatası: {str(e)}")
            return f"{self.theme_name} araştırması sırasında hata: {str(e)}"

class MainTripPlannerAgent:
    """Ana Agent - Bilgileri toplar ve JSON formatlar"""
    
    def __init__(self):
        # Research agent'ları oluştur
        self.researchers = {
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
        logger.info(f"📋 {len(self.researchers)} research agent hazır")

    def generate_trip_plan(self, prompt_data: Dict[str, Any]) -> str:
        """Ana koordinasyon fonksiyonu - paralel araştırma ve JSON formatlama"""
        try:
            logger.info("🚀 Main Agent: Sıralı araştırma başlıyor...")
            
            # Tarih hesapla
            start_date = datetime.strptime(prompt_data['start_date'], "%Y-%m-%d")
            end_date = datetime.strptime(prompt_data['end_date'], "%Y-%m-%d")
            total_days = (end_date - start_date).days + 1
            
            # Trip data hazırla
            trip_data = {
                **prompt_data,
                'total_days': total_days
            }
            
            # Research agent'larını SİRA İLE çalıştır
            research_results = self._run_research_parallel(trip_data)  # İsim aynı kalsın ama artık sıralı
            
            logger.info(f"✅ Main Agent: 3 tema için araştırma tamamlandı")
            
            # Araştırma sonuçlarını JSON'a çevir
            final_json = self._create_json_from_research(research_results, trip_data)
            
            logger.info(f"✅ Main Agent: JSON formatı başarıyla oluşturuldu")
            return final_json
            
        except Exception as e:
            logger.error(f"❌ Main Agent hatası: {str(e)}")
            return self._create_fallback_json(prompt_data)

    def _run_research_parallel(self, trip_data: Dict) -> Dict[str, str]:
        """Research agent'larını SIRA İLE çalıştır (paralel yerine)"""
        research_results = {}
        
        # Sıralı çalıştırma - paralel sorunları önlemek için
        for agent_name, agent in self.researchers.items():
            try:
                logger.info(f"🔄 {agent_name} research başlatılıyor...")
                result = agent.research_camps(trip_data)
                research_results[agent_name] = result
                logger.info(f"✅ {agent_name} research tamamlandı")
            except Exception as e:
                logger.error(f"❌ {agent_name} research hatası: {str(e)}")
                research_results[agent_name] = f"{agent_name} araştırması başarısız: {str(e)}"
        
        return research_results

    def _create_json_from_research(self, research_results: Dict[str, str], trip_data: Dict) -> str:
        """Araştırma sonuçlarını JSON formatına çevir"""
        try:
            trip_options = []
            
            theme_info = {
                "doğal": {
                    "theme": "Doğal Güzellikler Rotası",
                    "description": "Göller, şelaleler ve ormanlık alanlar gibi doğal harikaları keşfeden bir rota."
                },
                "tarihi": {
                    "theme": "Tarihi Güzellikler Rotası",
                    "description": "Antik kentler, kaleler ve tarihi yapılar gibi kültürel mirasları barındıran bir rota."
                },
                "macera": {
                    "theme": "Macera ve Aksiyon Rotası",
                    "description": "Dağcılık, rafting, yamaç paraşütü gibi aktivitelere uygun kamp alanlarını içeren bir rota."
                }
            }
            
            for agent_name, research_text in research_results.items():
                theme_data = theme_info.get(agent_name, {
                    "theme": "Bilinmeyen Tema",
                    "description": "Tema açıklaması bulunamadı"
                })
                
                # Research metninden kamp bilgilerini çıkar
                camp_info = self._extract_camp_info(research_text, trip_data)
                
                trip_option = {
                    "theme": theme_data["theme"],
                    "description": theme_data["description"],
                    "trip": {
                        "user_id": trip_data['user_id'],
                        "name": f"{trip_data['name']} - {theme_data['theme']}",
                        "description": trip_data['description'],
                        "start_position": trip_data['start_position'],
                        "end_position": trip_data['end_position'],
                        "start_date": trip_data['start_date'],
                        "end_date": trip_data['end_date'],
                        "total_days": trip_data['total_days']
                    },
                    "daily_plan": camp_info
                }
                
                trip_options.append(trip_option)
            
            final_response = {
                "trip_options": trip_options
            }
            
            return json.dumps(final_response, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ JSON oluşturma hatası: {str(e)}")
            return self._create_fallback_json(trip_data)

    def _extract_camp_info(self, research_text: str, trip_data: Dict) -> List[Dict]:
        """Research metninden kamp bilgilerini çıkar"""
        try:
            daily_plans = []
            
            # Basit regex ile kamp bilgilerini çıkarmaya çalış
            camp_pattern = r"KAMP YERİ \d+:(.*?)(?=KAMP YERİ \d+:|$)"
            camps = re.findall(camp_pattern, research_text, re.DOTALL | re.IGNORECASE)
            
            if not camps:
                # Alternatif pattern dene
                lines = research_text.split('\n')
                current_camp = {}
                
                for line in lines:
                    line = line.strip()
                    if line.lower().startswith('- i̇sim:') or line.lower().startswith('- isim:'):
                        if current_camp:
                            daily_plans.append(self._create_daily_plan_from_camp(current_camp, len(daily_plans) + 1, trip_data))
                        current_camp = {'name': line.split(':', 1)[1].strip()}
                    elif line.lower().startswith('- adres:'):
                        current_camp['address'] = line.split(':', 1)[1].strip()
                    elif line.lower().startswith('- web sitesi:') or line.lower().startswith('- website:'):
                        current_camp['site_url'] = line.split(':', 1)[1].strip()
                    elif line.lower().startswith('- latitude:'):
                        try:
                            current_camp['latitude'] = float(line.split(':', 1)[1].strip())
                        except:
                            current_camp['latitude'] = 39.0
                    elif line.lower().startswith('- longitude:'):
                        try:
                            current_camp['longitude'] = float(line.split(':', 1)[1].strip())
                        except:
                            current_camp['longitude'] = 35.0
                
                # Son kamp alanını da ekle
                if current_camp:
                    daily_plans.append(self._create_daily_plan_from_camp(current_camp, len(daily_plans) + 1, trip_data))
            
            else:
                # Regex ile bulunan kampları işle
                for i, camp_text in enumerate(camps[:trip_data['total_days']]):  # Maksimum gün sayısı kadar
                    camp_info = self._parse_camp_text(camp_text.strip())
                    daily_plans.append(self._create_daily_plan_from_camp(camp_info, i + 1, trip_data))
            
            # En az 1 günlük plan olsun
            if not daily_plans:
                daily_plans.append({
                    "day": 1,
                    "date": trip_data['start_date'],
                    "location": {
                        "name": "Varsayılan Kamp Alanı",
                        "address": f"{trip_data['start_position']} yakını kamp alanı",
                        "site_url": "",
                        "latitude": 39.0,
                        "longitude": 35.0
                    }
                })
            
            return daily_plans[:trip_data['total_days']]  # Maksimum gün sayısı kadar döndür
            
        except Exception as e:
            logger.error(f"❌ Kamp bilgisi çıkarma hatası: {str(e)}")
            return [{
                "day": 1,
                "date": trip_data['start_date'],
                "location": {
                    "name": "Varsayılan Kamp Alanı",
                    "address": f"{trip_data['start_position']} yakını",
                    "site_url": "",
                    "latitude": 39.0,
                    "longitude": 35.0
                }
            }]

    def _parse_camp_text(self, camp_text: str) -> Dict:
        """Tek bir kamp metnini parse et"""
        camp_info = {
            'name': 'Bilinmeyen Camping',
            'address': 'Adres bilgisi yok',
            'site_url': '',
            'latitude': 39.0,
            'longitude': 35.0
        }
        
        lines = camp_text.split('\n')
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace('-', '').strip()
                value = value.strip()
                
                if 'isim' in key or 'i̇sim' in key or 'name' in key:
                    camp_info['name'] = value
                elif 'adres' in key or 'address' in key:
                    camp_info['address'] = value
                elif 'web' in key or 'site' in key or 'url' in key:
                    camp_info['site_url'] = value
                elif 'latitude' in key or 'lat' in key:
                    try:
                        camp_info['latitude'] = float(value)
                    except:
                        pass
                elif 'longitude' in key or 'lng' in key or 'lon' in key:
                    try:
                        camp_info['longitude'] = float(value)
                    except:
                        pass
        
        return camp_info

    def _create_daily_plan_from_camp(self, camp_info: Dict, day: int, trip_data: Dict) -> Dict:
        """Kamp bilgisinden daily plan oluştur"""
        # Tarihi hesapla
        start_date = datetime.strptime(trip_data['start_date'], "%Y-%m-%d")
        current_date = start_date + timedelta(days=day - 1)
        
        return {
            "day": day,
            "date": current_date.strftime("%Y-%m-%d"),
            "location": {
                "name": camp_info.get('name', f'Camping {day}'),
                "address": camp_info.get('address', 'Adres bilgisi yok'),
                "site_url": camp_info.get('site_url', ''),
                "latitude": camp_info.get('latitude', 39.0),
                "longitude": camp_info.get('longitude', 35.0)
            }
        }

    def _create_fallback_json(self, trip_data: Dict) -> str:
        """Fallback JSON oluştur"""
        try:
            start_date = datetime.strptime(trip_data['start_date'], "%Y-%m-%d")
            end_date = datetime.strptime(trip_data['end_date'], "%Y-%m-%d")
            total_days = (end_date - start_date).days + 1
        except:
            total_days = 3
        
        fallback_data = {
            "trip_options": [
                {
                    "theme": "Doğal Güzellikler Rotası",
                    "description": "Göller, şelaleler ve ormanlık alanlar gibi doğal harikaları keşfeden bir rota.",
                    "trip": {
                        "user_id": trip_data['user_id'],
                        "name": f"{trip_data['name']} - Doğal Güzellikler Rotası",
                        "description": trip_data['description'],
                        "start_position": trip_data['start_position'],
                        "end_position": trip_data['end_position'],
                        "start_date": trip_data['start_date'],
                        "end_date": trip_data['end_date'],
                        "total_days": total_days
                    },
                    "daily_plan": [{
                        "day": 1,
                        "date": trip_data.get('start_date', '2024-01-01'),
                        "location": {
                            "name": "Varsayılan Doğal Kamp Alanı",
                            "address": f"{trip_data['start_position']} yakını doğal kamp alanı",
                            "site_url": "",
                            "latitude": 39.0,
                            "longitude": 35.0
                        }
                    }]
                },
                {
                    "theme": "Tarihi Güzellikler Rotası",
                    "description": "Antik kentler, kaleler ve tarihi yapılar gibi kültürel mirasları barındıran bir rota.",
                    "trip": {
                        "user_id": trip_data['user_id'],
                        "name": f"{trip_data['name']} - Tarihi Güzellikler Rotası",
                        "description": trip_data['description'],
                        "start_position": trip_data['start_position'],
                        "end_position": trip_data['end_position'],
                        "start_date": trip_data['start_date'],
                        "end_date": trip_data['end_date'],
                        "total_days": total_days
                    },
                    "daily_plan": [{
                        "day": 1,
                        "date": trip_data.get('start_date', '2024-01-01'),
                        "location": {
                            "name": "Varsayılan Tarihi Kamp Alanı",
                            "address": f"{trip_data['start_position']} yakını tarihi kamp alanı",
                            "site_url": "",
                            "latitude": 39.1,
                            "longitude": 35.1
                        }
                    }]
                },
                {
                    "theme": "Macera ve Aksiyon Rotası",
                    "description": "Dağcılık, rafting, yamaç paraşütü gibi aktivitelere uygun kamp alanlarını içeren bir rota.",
                    "trip": {
                        "user_id": trip_data['user_id'],
                        "name": f"{trip_data['name']} - Macera ve Aksiyon Rotası",
                        "description": trip_data['description'],
                        "start_position": trip_data['start_position'],
                        "end_position": trip_data['end_position'],
                        "start_date": trip_data['start_date'],
                        "end_date": trip_data['end_date'],
                        "total_days": total_days
                    },
                    "daily_plan": [{
                        "day": 1,
                        "date": trip_data.get('start_date', '2024-01-01'),
                        "location": {
                            "name": "Varsayılan Macera Kamp Alanı",
                            "address": f"{trip_data['start_position']} yakını macera kamp alanı",
                            "site_url": "",
                            "latitude": 39.2,
                            "longitude": 35.2
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