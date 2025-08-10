import grpc
from concurrent import futures
import json
import logging
import os
from typing import Dict, Any

# Proto dosyalarını import et
import route_guide_pb2 as grpc_server_pb2
import route_guide_pb2_grpc as grpc_server_pb2_grpc

from ai_agents import ai_agent

# Logging konfigürasyonu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AIService(grpc_server_pb2_grpc.AIServiceServicer):
    def __init__(self):
        """AI Service'i başlat"""
        try:
            self.agent = ai_agent()
            logger.info("✅ AI Agent başarıyla başlatıldı")
        except Exception as e:
            logger.error(f"❌ AI Agent başlatılamadı: {str(e)}")
            raise

    def GeneratePlan(self, request: grpc_server_pb2.PromptRequest, context) -> grpc_server_pb2.TripOptionsResponse:
        """
        3 farklı tema için seyahat planları oluşturur - UPDATED FOR 3 THEMES
        """
        try:
            logger.info(f"📥 gRPC Request alındı: {request}")
            
            # Request'ten veriyi çıkar
            prompt_data = {
                'user_id': request.user_id,
                'name': request.name,
                'description': request.description,
                'start_position': request.start_position,
                'end_position': request.end_position,
                'start_date': request.start_date,
                'end_date': request.end_date
            }
            
            logger.info(f"📊 Prompt verisi hazırlandı: {prompt_data}")
            
            # AI agent'tan plan al
            ai_response = self.agent.generate_trip_plan(prompt_data)
            logger.info(f"🧠 AI'dan gelen yanıt uzunluğu: {len(ai_response)} karakter")
            
            # Yanıtı debug için logla (ilk 500 karakter)
            logger.info(f"🔍 AI Response (ilk 500 kar): {ai_response[:500]}...")
            
            # JSON parse et
            try:
                parsed_response = json.loads(ai_response)
                logger.info("✅ JSON başarıyla parse edildi")
                
                # trip_options var mı kontrol et
                if 'trip_options' not in parsed_response:
                    logger.error("❌ 'trip_options' key'i JSON'da yok!")
                    logger.info(f"🔍 Mevcut keys: {list(parsed_response.keys())}")
                    return self._create_fallback_options_response(request)
                
                trip_options_data = parsed_response['trip_options']
                if not isinstance(trip_options_data, list):
                    logger.error("❌ 'trip_options' bir list değil!")
                    return self._create_fallback_options_response(request)
                
                if len(trip_options_data) == 0:
                    logger.warning("⚠️ 'trip_options' boş array!")
                    return self._create_fallback_options_response(request)
                    
                logger.info(f"✅ trip_options bulundu, tema sayısı: {len(trip_options_data)}")
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON parse hatası: {str(e)}")
                logger.error(f"🔍 Parse edilemeyen content: {ai_response}")
                return self._create_fallback_options_response(request)
            
            # Proto response oluştur
            response = self._create_trip_options_response(parsed_response)
            logger.info(f"🎯 gRPC response hazırlandı. Trip options: {len(response.trip_options)}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ GeneratePlan hatası: {str(e)}")
            logger.error(f"🔍 Exception detayları", exc_info=True)
            context.set_details(f"Internal server error: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return self._create_fallback_options_response(request)

    def _create_trip_options_response(self, parsed_data: Dict[Any, Any]) -> grpc_server_pb2.TripOptionsResponse:
        """JSON verisini TripOptionsResponse'a çevir - YENİ METHOD"""
        try:
            trip_options = []
            
            # trip_options array'ini kontrol et
            options_data = parsed_data.get('trip_options', [])
            
            if not options_data:
                logger.warning("⚠️ trip_options array'i boş veya bulunamadı")
                return self._create_empty_options_response()
            
            logger.info(f"🔄 {len(options_data)} tema işleniyor...")
            
            for i, option_data in enumerate(options_data):
                try:
                    logger.info(f"🔄 Tema {i+1} işleniyor: {option_data.get('theme', 'Unknown')}")
                    
                    # Daily plans oluştur
                    daily_plans = []
                    daily_plan_data = option_data.get('daily_plan', [])
                    
                    logger.info(f"📅 Tema {i+1} için {len(daily_plan_data)} günlük plan var")
                    
                    for j, daily in enumerate(daily_plan_data):
                        try:
                            location_data = daily.get('location', {})
                            
                            # Koordinatları kontrol et ve çevir
                            latitude = 0.0
                            longitude = 0.0
                            
                            if 'latitude' in location_data:
                                try:
                                    latitude = float(location_data['latitude'])
                                except (ValueError, TypeError):
                                    logger.warning(f"⚠️ Tema {i+1} Gün {j+1}: Geçersiz latitude")
                                    latitude = 39.0 + (i * 0.1)
                                    
                            if 'longitude' in location_data:
                                try:
                                    longitude = float(location_data['longitude'])
                                except (ValueError, TypeError):
                                    logger.warning(f"⚠️ Tema {i+1} Gün {j+1}: Geçersiz longitude")
                                    longitude = 35.0 + (i * 0.1)
                            
                            daily_plan = grpc_server_pb2.DailyPlan(
                                day=daily.get('day', j + 1),
                                date=daily.get('date', ''),
                                location=grpc_server_pb2.Location(
                                    name=location_data.get('name', f'Kamp Alanı {j+1}'),
                                    address=location_data.get('address', 'Adres bilgisi yok'),
                                    site_url=location_data.get('site_url', ''),
                                    latitude=latitude,
                                    longitude=longitude,
                                    notes=location_data.get('notes', '')
                                )
                            )
                            daily_plans.append(daily_plan)
                            logger.info(f"✅ Tema {i+1} Gün {j+1} oluşturuldu: {location_data.get('name', 'Unknown')}")
                            
                        except Exception as e:
                            logger.error(f"❌ Tema {i+1} Gün {j+1} oluşturma hatası: {str(e)}")
                            # Hata durumunda varsayılan gün oluştur
                            daily_plan = grpc_server_pb2.DailyPlan(
                                day=j + 1,
                                date='2024-01-01',
                                location=grpc_server_pb2.Location(
                                    name=f'Varsayılan Kamp Alanı {j+1}',
                                    address='Varsayılan adres',
                                    site_url='',
                                    latitude=39.0 + (i * 0.1),
                                    longitude=35.0 + (i * 0.1),
                                    notes='Hata nedeniyle varsayılan konum'
                                )
                            )
                            daily_plans.append(daily_plan)
                            continue
                        
                    logger.info(f"📍 Tema {i+1}: {len(daily_plans)} günlük plan oluşturuldu")
                    
                    # Trip oluştur
                    trip_data = option_data.get('trip', {})
                    
                    # total_days'i kontrol et ve çevir
                    total_days = 1
                    if 'total_days' in trip_data:
                        try:
                            total_days = int(trip_data['total_days'])
                        except (ValueError, TypeError):
                            logger.warning(f"⚠️ Tema {i+1}: Geçersiz total_days")
                            total_days = len(daily_plans) if daily_plans else 1
                    
                    trip = grpc_server_pb2.Trip(
                        user_id=trip_data.get('user_id', ''),
                        name=trip_data.get('name', f'Tema {i+1}'),
                        description=trip_data.get('description', ''),
                        start_position=trip_data.get('start_position', ''),
                        end_position=trip_data.get('end_position', ''),
                        start_date=trip_data.get('start_date', ''),
                        end_date=trip_data.get('end_date', ''),
                        total_days=total_days,
                        route_summary=trip_data.get('route_summary', '')
                    )
                    
                    # Trip option oluştur
                    trip_option = grpc_server_pb2.TripOption(
                        theme=option_data.get('theme', f'Tema {i+1}'),
                        description=option_data.get('description', ''),
                        trip=trip,
                        daily_plan=daily_plans
                    )
                    trip_options.append(trip_option)
                    
                    logger.info(f"✅ Tema {i+1} başarıyla oluşturuldu: {option_data.get('theme', f'Tema {i+1}')}")
                    
                except Exception as e:
                    logger.error(f"❌ Tema {i+1} oluşturma hatası: {str(e)}")
                    logger.error(f"🔍 Tema {i+1} data: {option_data}")
                    continue
            
            if not trip_options:
                logger.warning("⚠️ Hiç tema oluşturulamadı, fallback response dönüyor")
                return self._create_empty_options_response()
            
            logger.info(f"🎯 Toplam {len(trip_options)} tema başarıyla oluşturuldu")
            return grpc_server_pb2.TripOptionsResponse(
                trip_options=trip_options
            )
            
        except Exception as e:
            logger.error(f"❌ Trip options response oluşturma hatası: {str(e)}")
            logger.error(f"🔍 Parsed data keys: {list(parsed_data.keys()) if isinstance(parsed_data, dict) else 'Not dict'}")
            return self._create_empty_options_response()

    def _create_fallback_options_response(self, request: grpc_server_pb2.PromptRequest) -> grpc_server_pb2.TripOptionsResponse:
        """Hata durumunda fallback TripOptionsResponse oluştur - YENİ METHOD"""
        try:
            # 3 adet fallback tema oluştur
            fallback_themes = [
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
            
            for i, theme_info in enumerate(fallback_themes):
                # Fallback trip
                fallback_trip = grpc_server_pb2.Trip(
                    user_id=request.user_id,
                    name=f"{theme_info['theme']} - {request.name}",
                    description=theme_info['description'],
                    start_position=request.start_position,
                    end_position=request.end_position,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    total_days=3,  # Varsayılan 3 gün
                    route_summary=f"{request.start_position} - {request.end_position} {theme_info['theme'].lower()}"
                )
                
                # Fallback location
                fallback_location = grpc_server_pb2.Location(
                    name=f"{theme_info['theme'].split()[0]} Kamp Alanı",
                    address=f"{request.start_position} yakını {theme_info['theme'].lower()} temalı kamp alanı",
                    site_url="",
                    latitude=39.0 + i * 0.1,
                    longitude=35.0 + i * 0.1,
                    notes=f"Varsayılan {theme_info['theme'].lower()} temalı kamp alanı"
                )
                
                # Fallback daily plan
                fallback_daily = grpc_server_pb2.DailyPlan(
                    day=1,
                    date=request.start_date,
                    location=fallback_location
                )
                
                # Trip option oluştur
                trip_option = grpc_server_pb2.TripOption(
                    theme=theme_info["theme"],
                    description=theme_info["description"],
                    trip=fallback_trip,
                    daily_plan=[fallback_daily]
                )
                
                trip_options.append(trip_option)
            
            logger.info(f"🔧 Fallback response oluşturuldu: {len(trip_options)} tema")
            return grpc_server_pb2.TripOptionsResponse(
                trip_options=trip_options
            )
            
        except Exception as e:
            logger.error(f"❌ Fallback response oluşturma hatası: {str(e)}")
            return self._create_empty_options_response()

    def _create_empty_options_response(self) -> grpc_server_pb2.TripOptionsResponse:
        """Boş TripOptionsResponse oluştur"""
        logger.warning("⚠️ Boş trip options response oluşturuluyor")
        return grpc_server_pb2.TripOptionsResponse(
            trip_options=[]
        )

def serve(port: str = "50051"):
    """gRPC server'ı başlat"""
    try:
        # Server oluştur
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        
        # AI Service'i ekle
        ai_service = AIService()
        grpc_server_pb2_grpc.add_AIServiceServicer_to_server(ai_service, server)
        
        # Port'u dinle
        listen_addr = f'[::]:{port}'
        server.add_insecure_port(listen_addr)
        
        # Server'ı başlat
        server.start()
        logger.info(f"🚀 gRPC server {port} portunda başlatıldı")
        logger.info(f"📡 Dinlenen adres: {listen_addr}")
        
        # Graceful shutdown için bekle
        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            logger.info("🛑 Server kapatılıyor...")
            server.stop(0)
            
    except Exception as e:
        logger.error(f"❌ Server başlatma hatası: {str(e)}")
        raise

if __name__ == '__main__':
    # Environment'dan port al veya default kullan
    port = os.getenv('GRPC_PORT', '50051')
    serve(port)