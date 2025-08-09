import re
import json
import logging
import markdownify
import requests
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Union
from smolagents import CodeAgent, WebSearchTool, tool, OpenAIServerModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

        # API key'i environment'dan al
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            logger.error("❌ OPENROUTER_API_KEY environment variable bulunamadı!")
            raise ValueError("OPENROUTER_API_KEY gerekli!")

        # Model konfigürasyonu
        model = OpenAIServerModel(
            model_id="google/gemini-2.5-flash",  # Daha stabil model
            api_base="https://openrouter.ai/api/v1",
            api_key=api_key,
            max_tokens=8000,
        )

        # Agent'ı oluştur
        self.agent = CodeAgent(
            instructions=system_prompt,
            tools=[WebSearchTool(), visit_webpage],
            model=model,
            stream_outputs=True,
            additional_authorized_imports=[
                "time", "numpy", "pandas", "requests", "json", "re", 
                "collections", "statistics", "datetime", "time", 
                "itertools", "stat", "random", "unicodedata", 
                "math", "re", "queue"
            ],
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
            
            # Tarih aralığını hesapla
            start_date = datetime.strptime(prompt_data['start_date'], "%Y-%m-%d")
            end_date = datetime.strptime(prompt_data['end_date'], "%Y-%m-%d")
            total_days = (end_date - start_date).days + 1
            
            # User prompt oluştur
            user_prompt = f"""
            Lütfen aşağıdaki bilgilere göre bir seyahat planı oluştur ve SADECE JSON formatında yanıt ver:
            
            📋 Bilgiler:
            - Kullanıcı ID: {prompt_data['user_id']}
            - Plan Adı: {prompt_data['name']}
            - Açıklama: {prompt_data['description']}
            - Başlangıç Noktası: {prompt_data['start_position']}
            - Bitiş Noktası: {prompt_data['end_position']}
            - Başlangıç Tarihi: {prompt_data['start_date']}
            - Bitiş Tarihi: {prompt_data['end_date']}
            - Toplam Gün: {total_days}
            
            ⚠️ KRİTİK: 
            1. SADECE JSON formatında yanıt ver
            2. JSON syntax'ının mükemmel olduğundan emin ol
            3. Tekrar eden key'ler olmasın
            4. Tüm virgül ve parantezler doğru olsun
            5. final_answer() fonksiyonunu kullan
            
            Beklenen format:
            {{
              "trip": {{ ... }},
              "daily_plan": [ ... ]
            }}
            """
            
            logger.info("🤖 AI Agent çalıştırılıyor...")
            
            # Agent'ı çalıştır - daha kontrollü
            try:
                result = self.agent.run(user_prompt)
                logger.info(f"🧠 AI'dan gelen sonuç tipi: {type(result)}")
                
                # Result tipi kontrolü
                if isinstance(result, dict):
                    # AI doğrudan dict döndürmüş, JSON'a çevir
                    logger.info("✅ AI dict objesi döndürdü, JSON'a çeviriliyor...")
                    cleaned_result = json.dumps(result, ensure_ascii=False, indent=2)
                    # Validate et
                    if self._validate_json_structure(result):
                        logger.info("✅ Dict objesi geçerli yapıda")
                        return cleaned_result
                    else:
                        logger.warning("⚠️ Dict objesi yapısı geçersiz, fallback kullanılıyor")
                        return self._create_fallback_json(prompt_data)
                elif isinstance(result, str):
                    logger.info(f"🧠 AI string döndürdü, uzunluk: {len(result)} karakter")
                    # String ise normal extraction yap
                    cleaned_result = self._extract_and_validate_json(result, prompt_data)
                    return cleaned_result
                else:
                    logger.warning(f"⚠️ Beklenmeyen result tipi: {type(result)}")
                    return self._create_fallback_json(prompt_data)
                
            except Exception as e:
                logger.error(f"❌ AI Agent çalıştırma hatası: {str(e)}")
                return self._create_fallback_json(prompt_data)
            
        except Exception as e:
            logger.error(f"❌ Seyahat planı oluşturma hatası: {str(e)}")
            return self._create_fallback_json(prompt_data)

    def _extract_and_validate_json(self, response: Union[str, dict], prompt_data: Dict[str, Any]) -> str:
        """JSON yanıtını çıkar, temizle ve validate et"""
        try:
            # Eğer zaten dict ise, direkt validate et
            if isinstance(response, dict):
                if self._validate_json_structure(response):
                    return json.dumps(response, ensure_ascii=False, indent=2)
                else:
                    logger.warning("⚠️ Dict yapısı geçersiz")
                    return self._create_fallback_json(prompt_data)
            
            # String ise extraction yap
            if not isinstance(response, str):
                logger.error(f"❌ Beklenmeyen response tipi: {type(response)}")
                return self._create_fallback_json(prompt_data)
            # Çeşitli JSON extraction stratejileri
            json_candidates = []
            
            # 1. Kod bloklarından çıkar
            code_block_pattern = r'```(?:json)?\s*(.*?)\s*```'
            matches = re.findall(code_block_pattern, response, re.DOTALL | re.IGNORECASE)
            json_candidates.extend(matches)
            
            # 2. { ile başlayan ve } ile biten blokları bul
            brace_pattern = r'(\{.*\})'
            matches = re.findall(brace_pattern, response, re.DOTALL)
            json_candidates.extend(matches)
            
            # 3. final_answer() içindeki JSON'u bul
            final_answer_pattern = r'final_answer\s*\(\s*(["\'])(.*?)\1\s*\)'
            matches = re.findall(final_answer_pattern, response, re.DOTALL)
            if matches:
                json_candidates.extend([match[1] for match in matches])
            
            # JSON candidates'ları dene
            for candidate in json_candidates:
                try:
                    # Temizle
                    cleaned = self._clean_json_string(candidate)
                    
                    # Parse dene
                    parsed = json.loads(cleaned)
                    
                    # Validate et
                    if self._validate_json_structure(parsed):
                        logger.info("✅ Geçerli JSON bulundu ve validate edildi")
                        return json.dumps(parsed, ensure_ascii=False, indent=2)
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"JSON candidate parse hatası: {str(e)}")
                    continue
            
            # Hiçbiri işe yaramadıysa fallback
            logger.warning("⚠️ Geçerli JSON bulunamadı, fallback oluşturuluyor")
            return self._create_fallback_json(prompt_data)
            
        except Exception as e:
            logger.error(f"❌ JSON extraction hatası: {str(e)}")
            return self._create_fallback_json(prompt_data)

    def _clean_json_string(self, json_str: str) -> str:
        """JSON string'i temizle"""
        # Başındaki ve sonundaki whitespace'leri temizle
        json_str = json_str.strip()
        
        # Escape karakterleri düzelt
        json_str = json_str.replace('\\"', '"')
        json_str = json_str.replace("\\n", "\n")
        json_str = json_str.replace("\\t", "\t")
        
        # Trailing comma'ları temizle
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        return json_str

    def _validate_json_structure(self, data: Dict) -> bool:
        """JSON yapısını validate et"""
        try:
            # Temel yapıyı kontrol et
            if not isinstance(data, dict):
                return False
                
            if 'trip' not in data or 'daily_plan' not in data:
                return False
                
            trip = data['trip']
            daily_plan = data['daily_plan']
            
            # Trip validasyonu
            required_trip_fields = ['user_id', 'name', 'description', 'start_position', 
                                  'end_position', 'start_date', 'end_date', 'total_days']
            for field in required_trip_fields:
                if field not in trip:
                    return False
            
            # Daily plan validasyonu
            if not isinstance(daily_plan, list) or len(daily_plan) == 0:
                return False
                
            for day in daily_plan:
                if not isinstance(day, dict):
                    return False
                if 'day' not in day or 'date' not in day or 'location' not in day:
                    return False
                    
                location = day['location']
                if not isinstance(location, dict):
                    return False
                if 'name' not in location or 'address' not in location:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ JSON validation hatası: {str(e)}")
            return False

    def _create_fallback_json(self, prompt_data: Dict[str, Any]) -> str:
        """Hata durumunda fallback JSON oluştur"""
        try:
            # Tarih hesaplamaları
            start_date = datetime.strptime(prompt_data['start_date'], "%Y-%m-%d")
            end_date = datetime.strptime(prompt_data['end_date'], "%Y-%m-%d")
            total_days = (end_date - start_date).days + 1
            
            # Günlük planlar oluştur
            daily_plans = []
            for day in range(min(3, total_days)):  # Maksimum 3 gün göster
                current_date = start_date + timedelta(days=day)
                
                daily_plans.append({
                    "day": day + 1,
                    "date": current_date.strftime("%Y-%m-%d"),
                    "location": {
                        "name": f"Kamp Alanı {day + 1}",
                        "address": f"{prompt_data['start_position']} yakını kamp alanı",
                        "site_url": "",
                        "latitude": 39.0 + day * 0.1,
                        "longitude": 35.0 + day * 0.1,
                        "notes": f"Gün {day + 1} kamp lokasyonu"
                    }
                })
            
            fallback_data = {
                "trip": {
                    "user_id": prompt_data['user_id'],
                    "name": prompt_data['name'],
                    "description": prompt_data['description'],
                    "start_position": prompt_data['start_position'],
                    "end_position": prompt_data['end_position'],
                    "start_date": prompt_data['start_date'],
                    "end_date": prompt_data['end_date'],
                    "total_days": total_days
                },
                "daily_plan": daily_plans
            }
            
            logger.info("🔧 Fallback JSON oluşturuldu")
            return json.dumps(fallback_data, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Fallback JSON oluşturma hatası: {str(e)}")
            # En basit fallback - hata durumunda bile çalışacak
            simple_fallback = {
                "trip": {
                    "user_id": prompt_data.get('user_id', ''),
                    "name": prompt_data.get('name', 'Kamp Rotası'),
                    "description": prompt_data.get('description', 'Plan oluşturulamadı'),
                    "start_position": prompt_data.get('start_position', ''),
                    "end_position": prompt_data.get('end_position', ''),
                    "start_date": prompt_data.get('start_date', ''),
                    "end_date": prompt_data.get('end_date', ''),
                    "total_days": 1
                },
                "daily_plan": [{
                    "day": 1,
                    "date": prompt_data.get('start_date', '2024-01-01'),
                    "location": {
                        "name": "Kamp Alanı",
                        "address": "Adres bilgisi mevcut değil",
                        "site_url": "",
                        "latitude": 39.0,
                        "longitude": 35.0,
                        "notes": "Varsayılan konum"
                    }
                }]
            }
            return json.dumps(simple_fallback, ensure_ascii=False, indent=2)