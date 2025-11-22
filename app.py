import os
import logging
from flask import Flask
from dotenv import load_dotenv

# Importa nossas rotas seguras
from routes.webhooks import webhooks_bp
from routes.clients import clients_bp

# Importa o scheduler
from services.scheduler import init_scheduler, get_scheduler_status

# Carrega configurações
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações de Segurança do Flask
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback_inseguro_apenas_dev')

# Registra as rotas (Entrada de Dados)
# Agora sua API responderá em: http://localhost:5000/api/webhook
app.register_blueprint(webhooks_bp, url_prefix='/api')
app.register_blueprint(clients_bp, url_prefix='/api')

# Rota de Saúde (Health Check)
@app.route('/', methods=['GET'])
def health_check():
    scheduler_status = get_scheduler_status()
    return {
        "status": "online",
        "system": "MVP CRM & Automation",
        "version": "1.0.0",
        "scheduler": scheduler_status
    }, 200

# Inicializa o scheduler quando a aplicação inicia
# IMPORTANTE: No Render, isso só funciona se o worker estiver sempre ativo
# Para produção, considere usar um worker separado ou cron jobs do Render
try:
    scheduler = init_scheduler(app)
    logger.info("✅ Aplicação inicializada com scheduler")
except Exception as e:
    logger.error(f"❌ Erro ao inicializar scheduler: {e}")
    scheduler = None

if __name__ == '__main__':
    # Em produção (Render), o host deve ser 0.0.0.0
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)