import os
from flask import Flask
from dotenv import load_dotenv

# Importa nossas rotas seguras
from routes.webhooks import webhooks_bp

# Carrega configurações
load_dotenv()

app = Flask(__name__)

# Configurações de Segurança do Flask
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback_inseguro_apenas_dev')

# Registra as rotas (Entrada de Dados)
# Agora sua API responderá em: http://localhost:5000/api/webhook
app.register_blueprint(webhooks_bp, url_prefix='/api')

# Rota de Saúde (Health Check)
@app.route('/', methods=['GET'])
def health_check():
    return {
        "status": "online",
        "system": "MVP CRM & Automation",
        "version": "1.0.0"
    }, 200

if __name__ == '__main__':
    # Em produção (Render), o host deve ser 0.0.0.0
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)