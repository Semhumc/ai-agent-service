#!/usr/bin/env python3
"""
AI Routes Service - gRPC Server
Kamp rotası planlama için AI tabanlı gRPC servisi
"""

import os
import sys
import logging
from grpc_server import serve

def setup_logging():
    """Logging konfigürasyonu"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('ai_routes_service.log')
        ]
    )

def main():
    """Ana fonksiyon"""
    try:
        print("🚀 AI Routes Service başlatılıyor...")
        
        # Logging'i ayarla
        setup_logging()
        logger = logging.getLogger(__name__)
        
        # Environment variables
        port = os.getenv('GRPC_PORT', '50051')
        
        logger.info("=" * 50)
        logger.info("🤖 AI ROUTES SERVICE")
        logger.info("=" * 50)
        logger.info(f"📡 Port: {port}")
        logger.info(f"🐍 Python: {sys.version}")
        logger.info("=" * 50)
        
        # API Key kontrolü
        if not os.getenv('OPENROUTER_API_KEY') and not os.path.exists('.env'):
            logger.warning("⚠️  OPENROUTER_API_KEY environment variable bulunamadı!")
            logger.warning("⚠️  .env dosyası oluşturun veya environment variable ekleyin")
        
        # Server'ı başlat
        serve(port)
        
    except KeyboardInterrupt:
        print("\n🛑 Kullanıcı tarafından durduruldu")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal hata: {str(e)}")
        logging.error(f"Fatal hata: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()