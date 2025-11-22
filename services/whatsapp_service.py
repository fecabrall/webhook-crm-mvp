"""
Serviço de integração com API de WhatsApp.
Atualmente implementado como MOCK para desenvolvimento.
Quando a API real estiver disponível, substitua as funções mock pelas chamadas reais.
"""
import os
import requests
import logging
from typing import Dict, Tuple, Optional

# Configuração de logging
logger = logging.getLogger(__name__)

# Variáveis de ambiente para API (quando disponível)
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")

# Modo MOCK (True = usa mock, False = usa API real)
MOCK_MODE = os.getenv("WHATSAPP_MOCK_MODE", "true").lower() == "true"


def send_follow_up_message(client_data: Dict) -> Tuple[bool, Optional[str]]:
    """
    Envia mensagem de acompanhamento para o cliente via WhatsApp.
    
    Args:
        client_data: Dicionário com dados do cliente (nome, telefone, etc.)
    
    Returns:
        Tuple[bool, Optional[str]]: (sucesso, mensagem_de_erro)
        - Se sucesso=True, a mensagem foi enviada
        - Se sucesso=False, retorna a mensagem de erro
    """
    try:
        nome = client_data.get('nome', 'Cliente')
        telefone = client_data.get('telefone', '')
        
        if not telefone:
            return False, "Telefone não fornecido"
        
        # Limpa o telefone (remove caracteres não numéricos)
        telefone_limpo = ''.join(filter(str.isdigit, telefone))
        
        if MOCK_MODE:
            # MODO MOCK - Simula envio de mensagem
            logger.info(f"[MOCK] Simulando envio de mensagem para {nome} ({telefone_limpo})")
            return _mock_send_message(nome, telefone_limpo)
        else:
            # MODO REAL - Chama API de WhatsApp
            return _real_send_message(nome, telefone_limpo, client_data)
            
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para {client_data.get('nome')}: {str(e)}")
        return False, f"Erro inesperado: {str(e)}"


def _mock_send_message(nome: str, telefone: str) -> Tuple[bool, Optional[str]]:
    """
    Simula o envio de mensagem (MOCK).
    Use esta função durante desenvolvimento até ter a API real.
    """
    mensagem = f"Olá {nome}! 👋\n\nObrigado por se tornar nosso cliente. Estamos aqui para ajudar!"
    
    # Simula delay de API
    import time
    time.sleep(0.1)
    
    # Simula sucesso (90% das vezes) para testes realistas
    import random
    if random.random() < 0.9:
        logger.info(f"✅ [MOCK] Mensagem enviada com sucesso para {telefone}")
        return True, None
    else:
        logger.warning(f"⚠️ [MOCK] Simulação de falha no envio para {telefone}")
        return False, "Erro simulado no envio (mock)"


def _real_send_message(nome: str, telefone: str, client_data: Dict) -> Tuple[bool, Optional[str]]:
    """
    Envia mensagem real via API de WhatsApp.
    Esta função será usada quando a API estiver configurada.
    
    Exemplo de integração com WhatsApp Business API:
    - Meta WhatsApp Business API
    - Twilio WhatsApp API
    - Evolution API
    - etc.
    """
    if not WHATSAPP_API_URL or not WHATSAPP_API_TOKEN:
        logger.error("Configuração da API de WhatsApp não encontrada")
        return False, "API de WhatsApp não configurada"
    
    try:
        # Formata telefone para formato internacional (ex: 5511987654321)
        telefone_formatado = _format_phone_number(telefone)
        
        # Monta a mensagem personalizada
        mensagem = f"Olá {nome}! 👋\n\nObrigado por se tornar nosso cliente. Estamos aqui para ajudar!"
        
        # Exemplo de payload para WhatsApp Business API (Meta)
        payload = {
            "messaging_product": "whatsapp",
            "to": telefone_formatado,
            "type": "text",
            "text": {
                "body": mensagem
            }
        }
        
        headers = {
            "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Faz a requisição para a API
        response = requests.post(
            f"{WHATSAPP_API_URL}/messages",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 201:
            logger.info(f"✅ Mensagem enviada com sucesso para {telefone_formatado}")
            return True, None
        else:
            error_msg = f"API retornou status {response.status_code}: {response.text}"
            logger.error(f"❌ Erro ao enviar mensagem: {error_msg}")
            return False, error_msg
            
    except requests.exceptions.Timeout:
        logger.error("Timeout ao conectar com API de WhatsApp")
        return False, "Timeout na conexão com API"
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição para API: {str(e)}")
        return False, f"Erro na requisição: {str(e)}"
    except Exception as e:
        logger.error(f"Erro inesperado: {str(e)}")
        return False, f"Erro inesperado: {str(e)}"


def _format_phone_number(telefone: str) -> str:
    """
    Formata telefone para formato internacional.
    Exemplo: 11987654321 -> 5511987654321
    """
    # Remove caracteres não numéricos
    telefone_limpo = ''.join(filter(str.isdigit, telefone))
    
    # Se não começar com código do país, adiciona (Brasil = 55)
    if not telefone_limpo.startswith('55') and len(telefone_limpo) >= 10:
        telefone_limpo = '55' + telefone_limpo
    
    return telefone_limpo


def send_custom_message(telefone: str, mensagem: str) -> Tuple[bool, Optional[str]]:
    """
    Envia uma mensagem customizada para um telefone.
    Útil para mensagens personalizadas além do follow-up automático.
    
    Args:
        telefone: Número do telefone
        mensagem: Texto da mensagem
    
    Returns:
        Tuple[bool, Optional[str]]: (sucesso, mensagem_de_erro)
    """
    client_data = {
        'nome': 'Cliente',
        'telefone': telefone
    }
    
    if MOCK_MODE:
        logger.info(f"[MOCK] Enviando mensagem customizada para {telefone}")
        return _mock_send_message("Cliente", telefone)
    else:
        # Para mensagem customizada, você pode adaptar o payload
        return _real_send_message("Cliente", telefone, client_data)

