"""
Scheduler para automação de tarefas agendadas.
Executa rotinas diárias para processar clientes e enviar mensagens de acompanhamento.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from services.database_service import get_clients_for_automation, update_client_status
from services.whatsapp_service import send_follow_up_message

# Configuração de logging
logger = logging.getLogger(__name__)

# Instância global do scheduler
scheduler = None


def init_scheduler(app=None):
    """
    Inicializa o scheduler e agenda as tarefas automáticas.
    
    Args:
        app: Instância do Flask app (opcional, para contexto de aplicação)
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler já está inicializado")
        return scheduler
    
    # Cria o scheduler em background
    scheduler = BackgroundScheduler(daemon=True)
    
    # Agenda a tarefa diária de automação
    # Executa todos os dias às 09:00 (ajuste conforme necessário)
    scheduler.add_job(
        func=job_diario_de_automacao,
        trigger=CronTrigger(hour=9, minute=0),  # 09:00 todos os dias
        id='automacao_diaria',
        name='Automação Diária - Envio de Mensagens',
        replace_existing=True,
        max_instances=1  # Evita execuções simultâneas
    )
    
    # Inicia o scheduler
    scheduler.start()
    logger.info("✅ Scheduler inicializado com sucesso")
    logger.info("📅 Tarefa agendada: Automação Diária às 09:00")
    
    return scheduler


def job_diario_de_automacao():
    """
    Job principal executado diariamente pelo scheduler.
    
    Responsabilidades:
    1. Busca clientes que precisam de acompanhamento
    2. Envia mensagens de follow-up via WhatsApp
    3. Atualiza status dos clientes no banco de dados
    """
    logger.info("=" * 50)
    logger.info("🚀 Iniciando automação diária de clientes")
    logger.info(f"⏰ Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    
    try:
        # 1. Busca clientes para processar
        clients, error = get_clients_for_automation()
        
        if error:
            logger.error(f"❌ Erro ao buscar clientes: {error}")
            return
        
        if not clients:
            logger.info("ℹ️ Nenhum cliente encontrado para processar")
            return
        
        logger.info(f"📊 Total de clientes encontrados: {len(clients)}")
        
        # 2. Processa cada cliente
        sucessos = 0
        falhas = 0
        
        for client in clients:
            client_id = client.get('id')
            client_nome = client.get('nome', 'Cliente sem nome')
            client_status = client.get('status', '')
            
            logger.info(f"\n📧 Processando cliente: {client_nome} (ID: {client_id})")
            
            # Verifica se o cliente já recebeu mensagem de acompanhamento
            # (evita spam - você pode ajustar essa lógica)
            if 'Acompanhamento enviado' in client_status:
                logger.info(f"⏭️ Cliente {client_nome} já recebeu acompanhamento. Pulando...")
                continue
            
            # 3. Envia mensagem de follow-up
            sucesso, erro = send_follow_up_message(client)
            
            if sucesso:
                sucessos += 1
                # 4. Atualiza status do cliente
                novo_status = f"{client_status} | Acompanhamento enviado em {datetime.now().strftime('%d/%m/%Y')}"
                update_success, update_error = update_client_status(client_id, novo_status)
                
                if update_success:
                    logger.info(f"✅ Cliente {client_nome} processado com sucesso")
                else:
                    logger.warning(f"⚠️ Mensagem enviada, mas falha ao atualizar status: {update_error}")
            else:
                falhas += 1
                logger.error(f"❌ Falha ao enviar mensagem para {client_nome}: {erro}")
        
        # 5. Resumo final
        logger.info("\n" + "=" * 50)
        logger.info("📈 RESUMO DA AUTOMAÇÃO DIÁRIA")
        logger.info(f"✅ Sucessos: {sucessos}")
        logger.info(f"❌ Falhas: {falhas}")
        logger.info(f"📊 Total processado: {len(clients)}")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"❌ Erro crítico na automação diária: {str(e)}", exc_info=True)


def stop_scheduler():
    """
    Para o scheduler (útil para testes ou shutdown graceful).
    """
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 Scheduler parado")
        scheduler = None


def get_scheduler_status():
    """
    Retorna o status atual do scheduler.
    """
    if scheduler is None:
        return {"status": "not_initialized"}
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        })
    
    return {
        "status": "running" if scheduler.running else "stopped",
        "jobs": jobs
    }

