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
            tools=[WebSearchTool()],
            model=model,
            max_steps=8,
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
        Verilen bilgilere dayanarak 3 temada seyahat planı oluşturur
        
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
            Lütfen aşağıdaki bilgilere göre 3 farklı temada kamp rotası planı oluştur ve SADECE JSON formatında yanıt ver:
            
            📋 Bilgiler:
            - Kullanıcı ID: {prompt_data['user_id']}
            - Plan Adı: {prompt_data['name']}
            - Açıklama: {prompt_data['description']}
            - Başlangıç Noktası: {prompt_data['start_position']}
            - Bitiş Noktası: {prompt_data['end_position']}
            - Başlangıç Tarihi: {prompt_data['start_date']}
            - Bitiş Tarihi: {prompt_data['end_date']}
            - Toplam Gün: {total_days}
            
            ⚠️ KRİTİK KURALLAR: 
            1. SADECE JSON formatında yanıt ver
            2. MUTLAKA "trip_options" array'i içinde TAM OLARAK 3 tema oluştur
            3. JSON syntax'ının mükemmel olduğundan emin ol
            4. Tekrar eden key'ler olmasın
            5. Tüm virgül ve parantezler doğru olsun
            6. final_answer() fonksiyonunu kullan
            7. Her temada farklı kamp alanları araştır ve gerçek bilgiler ver
            
            Beklenen format:
            {{
              "trip_options": [
                {{
                  "theme": "Tema Adı",
                  "description": "Tema açıklaması",
                  "trip": {{ ... }},
                  "daily_plan": [ ... ]
                }},
                ... 2 tema daha (toplam 3)
              ]
            }}
            
            ARAŞTIR ve GERÇEK KAMP ALANLARI BUL!
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
                    if self._validate_trip_options_structure(result):
                        logger.info("✅ Dict objesi geçerli yapıda")
                        return cleaned_result
                    else:
                        logger.warning("⚠️ Dict objesi yapısı geçersiz, fallback kullanılıyor")
                        return self._create_fallback_trip_options(prompt_data)
                elif isinstance(result, str):
                    logger.info(f"🧠 AI string döndürdü, uzunluk: {len(result)} karakter")
                    # String ise normal extraction yap
                    cleaned_result = self._extract_and_validate_trip_options_json(result, prompt_data)
                    return cleaned_result
                else:
                    logger.warning(f"⚠️ Beklenmeyen result tipi: {type(result)}")
                    return self._create_fallback_trip_options(prompt_data)
                
            except Exception as e:
                logger.error(f"❌ AI Agent çalıştırma hatası: {str(e)}")
                return self._create_fallback_trip_options(prompt_data)
            
        except Exception as e:
            logger.error(f"❌ Seyahat planı oluşturma hatası: {str(e)}")
            return self._create_fallback_trip_options(prompt_data)

    def _extract_and_validate_trip_options_json(self, response: Union[str, dict], prompt_data: Dict[str, Any]) -> str:
        """Trip options JSON yanıtını çıkar, temizle ve validate et"""
        try:
            # Eğer zaten dict ise, direkt validate et
            if isinstance(response, dict):
                if self._validate_trip_options_structure(response):
                    return json.dumps(response, ensure_ascii=False, indent=2)
                else:
                    logger.warning("⚠️ Dict yapısı geçersiz")
                    return self._create_fallback_trip_options(prompt_data)
            
            # String ise extraction yap
            if not isinstance(response, str):
                logger.error(f"❌ Beklenmeyen response tipi: {type(response)}")
                return self._create_fallback_trip_options(prompt_data)
            
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
            
            # 4. final_answer() içinde JSON objesi (string olmayan)
            final_answer_obj_pattern = r'final_answer\s*\(\s*(\{.*?\})\s*\)'
            matches = re.findall(final_answer_obj_pattern, response, re.DOTALL)
            json_candidates.extend(matches)
            
            # JSON candidates'ları dene
            for candidate in json_candidates:
                try:
                    # Temizle
                    cleaned = self._clean_json_string(candidate)
                    
                    # Parse dene
                    parsed = json.loads(cleaned)
                    
                    # Validate et - Trip options için özel validation
                    if self._validate_trip_options_structure(parsed):
                        logger.info("✅ Geçerli trip options JSON bulundu ve validate edildi")
                        return json.dumps(parsed, ensure_ascii=False, indent=2)
                        
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"JSON candidate parse hatası: {str(e)}")
                    continue
            
            # Hiçbiri işe yaramadıysa fallback
            logger.warning("⚠️ Geçerli trip options JSON bulunamadı, fallback oluşturuluyor")
            return self._create_fallback_trip_options(prompt_data)
            
        except Exception as e:
            logger.error(f"❌ JSON extraction hatası: {str(e)}")
            return self._create_fallback_trip_options(prompt_data)

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

    def _validate_trip_options_structure(self, data: Dict) -> bool:
        """Trip options JSON yapısını validate et"""
        try:
            # Temel yapıyı kontrol et
            if not isinstance(data, dict):
                logger.error("❌ Data dict değil")
                return False
                
            if 'trip_options' not in data:
                logger.error("❌ trip_options key'i bulunamadı")
                return False
                
            trip_options = data['trip_options']
            
            # Trip options array kontrolü
            if not isinstance(trip_options, list):
                logger.error("❌ trip_options list değil")
                return False
                
            if len(trip_options) != 3:
                logger.error(f"❌ Trip options sayısı 3 değil: {len(trip_options)}")
                return False
            
            # Her trip option'ı validate et
            for i, option in enumerate(trip_options):
                if not isinstance(option, dict):
                    logger.error(f"❌ Trip option {i} dict değil")
                    return False
                    
                # Gerekli alanları kontrol et
                required_option_fields = ['theme', 'description', 'trip', 'daily_plan']
                for field in required_option_fields:
                    if field not in option:
                        logger.error(f"❌ Trip option {i} içinde {field} yok")
                        return False
                
                # Trip validasyonu
                trip = option['trip']
                if not isinstance(trip, dict):
                    logger.error(f"❌ Trip {i} dict değil")
                    return False
                    
                required_trip_fields = ['user_id', 'name', 'description', 'start_position', 
                                      'end_position', 'start_date', 'end_date', 'total_days']
                for field in required_trip_fields:
                    if field not in trip:
                        logger.error(f"❌ Trip {i} içinde {field} yok")
                        return False
                
                # Daily plan validasyonu
                daily_plan = option['daily_plan']
                if not isinstance(daily_plan, list):
                    logger.error(f"❌ Daily plan {i} list değil")
                    return False
                    
                if len(daily_plan) == 0:
                    logger.error(f"❌ Daily plan {i} boş")
                    return False
                    
                for j, day in enumerate(daily_plan):
                    if not isinstance(day, dict):
                        logger.error(f"❌ Daily plan {i}.{j} dict değil")
                        return False
                    if 'day' not in day or 'date' not in day or 'location' not in day:
                        logger.error(f"❌ Daily plan {i}.{j} içinde gerekli alanlar yok")
                        return False
                        
                    location = day['location']
                    if not isinstance(location, dict):
                        logger.error(f"❌ Location {i}.{j} dict değil")
                        return False
                    if 'name' not in location or 'address' not in location:
                        logger.error(f"❌ Location {i}.{j} içinde name/address yok")
                        return False
            
            logger.info("✅ Trip options yapısı geçerli")
            return True
            
        except Exception as e:
            logger.error(f"❌ Trip options validation hatası: {str(e)}")
            return False

    def _create_fallback_trip_options(self, prompt_data: Dict[str, Any]) -> str:
        """Hata durumunda fallback trip options JSON oluştur"""
        try:
            # Tarih hesaplamaları
            start_date = datetime.strptime(prompt_data['start_date'], "%Y-%m-%d")
            end_date = datetime.strptime(prompt_data['end_date'], "%Y-%m-%d")
            total_days = (end_date - start_date).days + 1
            
            # 3 tema oluştur
            themes = [
                {
                    "theme": "Doğal Güzellikler Rotası",
                    "description": "Göller, şelaleler ve ormanlık alanlar gibi doğal harikaları keşfeden bir rota.",
                },
                {
                    "theme": "Tarihi Güzellikler Rotası", 
                    "description": "Antik kentler, kaleler ve tarihi yapılar gibi kültürel mirasları barındıran bir rota.",
                },
                {
                    "theme": "Macera ve Aksiyon Rotası",
                    "description": "Dağcılık, rafting, yamaç paraşütü gibi aktivitelere uygun kamp alanlarını içeren bir rota.",
                }
            ]
            
            trip_options = []
            
            for i, theme_info in enumerate(themes):
                # Günlük planlar oluştur
                daily_plans = []
                for day in range(min(3, total_days)):  # Maksimum 3 gün göster
                    current_date = start_date + timedelta(days=day)
                    
                    daily_plans.append({
                        "day": day + 1,
                        "date": current_date.strftime("%Y-%m-%d"),
                        "location": {
                            "name": f"{theme_info['theme'].split()[0]} Kamp Alanı {day + 1}",
                            "address": f"{prompt_data['start_position']} yakını {theme_info['theme'].lower()} temalı kamp alanı",
                            "site_url": "",
                            "latitude": 39.0 + (i * 0.1) + (day * 0.05),
                            "longitude": 35.0 + (i * 0.1) + (day * 0.05),
                        }
                    })
                
                # Trip option oluştur
                trip_option = {
                    "theme": theme_info["theme"],
                    "description": theme_info["description"],
                    "trip": {
                        "user_id": prompt_data['user_id'],
                        "name": f"{theme_info['theme']} - {prompt_data['name']}",
                        "description": prompt_data['description'],
                        "start_position": prompt_data['start_position'],
                        "end_position": prompt_data['end_position'],
                        "start_date": prompt_data['start_date'],
                        "end_date": prompt_data['end_date'],
                        "total_days": total_days
                    },
                    "daily_plan": daily_plans
                }
                
                trip_options.append(trip_option)
            
            fallback_data = {
                "trip_options": trip_options
            }
            
            logger.info("🔧 Fallback trip options JSON oluşturuldu")
            return json.dumps(fallback_data, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"❌ Fallback trip options oluşturma hatası: {str(e)}")
            # En basit fallback - hata durumunda bile çalışacak
            simple_fallback = {
                "trip_options": [
                    {
                        "theme": "Doğal Güzellikler Rotası",
                        "description": "Doğal güzellikleri keşfeden bir rota",
                        "trip": {
                            "user_id": prompt_data.get('user_id', ''),
                            "name": f"Doğal Güzellikler - {prompt_data.get('name', 'Kamp Rotası')}",
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
                                "name": "Doğal Kamp Alanı",
                                "address": "Adres bilgisi mevcut değil",
                                "site_url": "",
                                "latitude": 39.0,
                                "longitude": 35.0,
                            }
                        }]
                    },
                    {
                        "theme": "Tarihi Güzellikler Rotası",
                        "description": "Tarihi güzellikleri keşfeden bir rota",
                        "trip": {
                            "user_id": prompt_data.get('user_id', ''),
                            "name": f"Tarihi Güzellikler - {prompt_data.get('name', 'Kamp Rotası')}",
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
                                "name": "Tarihi Kamp Alanı",
                                "address": "Adres bilgisi mevcut değil",
                                "site_url": "",
                                "latitude": 39.1,
                                "longitude": 35.1,
                            }
                        }]
                    },
                    {
                        "theme": "Macera ve Aksiyon Rotası",
                        "description": "Macera aktivitelerini içeren bir rota",
                        "trip": {
                            "user_id": prompt_data.get('user_id', ''),
                            "name": f"Macera Rotası - {prompt_data.get('name', 'Kamp Rotası')}",
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
                                "name": "Macera Kamp Alanı",
                                "address": "Adres bilgisi mevcut değil",
                                "site_url": "",
                                "latitude": 39.2,
                                "longitude": 35.2,
                            }
                        }]
                    }
                ]
            }
            return json.dumps(simple_fallback, ensure_ascii=False, indent=2)