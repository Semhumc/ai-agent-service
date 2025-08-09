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

    def GeneratePlan(self, request: grpc_server_pb2.PromptRequest, context) -> grpc_server_pb2.TripPlanResponse:
        """
        Seyahat planı oluşturur - Go kodunuzla uyumlu method ismi
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
            
            # JSON parse et
            try:
                parsed_response = json.loads(ai_response)
                logger.info("✅ JSON başarıyla parse edildi")
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON parse hatası: {str(e)}")
                logger.info("🔧 Fallback response oluşturuluyor...")
                return self._create_fallback_response(request)
            
            # Proto response oluştur
            response = self._create_proto_response(parsed_response)
            logger.info(f"🎯 gRPC response hazırlandı. Daily plans: {len(response.daily_plan)}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ GeneratePlan hatası: {str(e)}")
            context.set_details(f"Internal server error: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            return self._create_fallback_response(request)

    def _create_proto_response(self, parsed_data: Dict[Any, Any]) -> grpc_server_pb2.TripPlanResponse:
        """JSON verisini Proto response'a çevir"""
        try:
            # Trip bilgilerini çıkar
            trip_data = parsed_data.get('trip', {})
            daily_plan_data = parsed_data.get('daily_plan', [])
            
            # Daily plans oluştur
            daily_plans = []
            for i, daily in enumerate(daily_plan_data):
                location_data = daily.get('location', {})
                
                daily_plan = grpc_server_pb2.DailyPlan(
                    day=daily.get('day', i + 1),
                    date=daily.get('date', ''),
                    location=grpc_server_pb2.Location(
                        name=location_data.get('name', ''),
                        address=location_data.get('address', ''),
                        site_url=location_data.get('site_url', ''),
                        latitude=float(location_data.get('latitude', 0.0)),
                        longitude=float(location_data.get('longitude', 0.0)),
                        notes=location_data.get('notes', '')
                    )
                )
                daily_plans.append(daily_plan)
                logger.info(f"📍 Day {daily_plan.day}: {location_data.get('name', 'Unknown')}")
            
            # Trip response oluştur
            trip = grpc_server_pb2.Trip(
                user_id=trip_data.get('user_id', ''),
                name=trip_data.get('name', ''),
                description=trip_data.get('description', ''),
                start_position=trip_data.get('start_position', ''),
                end_position=trip_data.get('end_position', ''),
                start_date=trip_data.get('start_date', ''),
                end_date=trip_data.get('end_date', ''),
                total_days=int(trip_data.get('total_days', 0)),
                route_summary=trip_data.get('route_summary', '')
            )
            
            return grpc_server_pb2.TripPlanResponse(
                trip=trip,
                daily_plan=daily_plans
            )
            
        except Exception as e:
            logger.error(f"❌ Proto response oluşturma hatası: {str(e)}")
            raise

    def _create_fallback_response(self, request: grpc_server_pb2.PromptRequest) -> grpc_server_pb2.TripPlanResponse:
        """Hata durumunda fallback response oluştur"""
        fallback_trip = grpc_server_pb2.Trip(
            user_id=request.user_id,
            name=request.name,
            description=request.description,
            start_position=request.start_position,
            end_position=request.end_position,
            start_date=request.start_date,
            end_date=request.end_date,
            total_days=7,
            route_summary="Kamp rotası planlandı. Detaylar için sistem yöneticisi ile iletişime geçin."
        )
        
        fallback_location = grpc_server_pb2.Location(
            name="Kamp Alanı 1",
            address=f"{request.start_position} yakını",
            site_url="",
            latitude=39.0,
            longitude=35.0,
            notes="Güzel kamp alanı"
        )
        
        fallback_daily = grpc_server_pb2.DailyPlan(
            day=1,
            date=request.start_date,
            location=fallback_location
        )
        
        return grpc_server_pb2.TripPlanResponse(
            trip=fallback_trip,
            daily_plan=[fallback_daily]
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