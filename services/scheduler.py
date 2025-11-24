"""
Scheduler para automação de tarefas agendadas.
Executa rotinas diárias para processar clientes e enviar mensagens de acompanhamento.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from services.database_service import (
    get_clients_for_automation, 
    update_client_status,
    get_clients_needing_action,
    insert_action,
    update_client_next_action
)
from services.whatsapp_service import send_follow_up_message
from datetime import datetime, timedelta

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
        # 1. Busca clientes que precisam de ação (baseado em data_primeira_compra)
        # Padrão: 7 dias após a compra
        clients, error = get_clients_needing_action(days_after_purchase=7)
        
        if error:
            logger.error(f"❌ Erro ao buscar clientes: {error}")
            return
        
        if not clients:
            logger.info("ℹ️ Nenhum cliente encontrado que precise de ação hoje")
            return
        
        logger.info(f"📊 Total de clientes que precisam de ação: {len(clients)}")
        
        # 2. Processa cada cliente
        sucessos = 0
        falhas = 0
        
        for client in clients:
            client_id = client.get('id')
            client_nome = client.get('nome', 'Cliente sem nome')
            client_status = client.get('status', '')
            data_compra = client.get('data_primeira_compra')
            
            logger.info(f"\n📧 Processando cliente: {client_nome} (ID: {client_id})")
            
            # 3. Cria registro de ação pendente
            acao_data = {
                'id_cliente': client_id,
                'tipo': 'mensagem',
                'conteudo': f'Mensagem de acompanhamento automática para {client_nome}',
                'resultado': 'pendente',
                'data': datetime.now().isoformat()
            }
            
            acao_criada, erro_acao = insert_action(acao_data)
            if not acao_criada:
                logger.error(f"❌ Erro ao criar ação para {client_nome}: {erro_acao}")
                falhas += 1
                continue
            
            # 4. Envia mensagem de follow-up
            sucesso, erro = send_follow_up_message(client)
            
            if sucesso:
                sucessos += 1
                # 5. Atualiza a ação como concluída
                update_action_result(acao_criada['id'], 'sim')
                
                # 6. Atualiza status do cliente e próxima ação
                novo_status = f"{client_status} | Acompanhamento enviado em {datetime.now().strftime('%d/%m/%Y')}"
                update_client_status(client_id, novo_status)
                
                # Agenda próxima ação (14 dias após a compra)
                if data_compra:
                    try:
                        if isinstance(data_compra, str):
                            data_compra_obj = datetime.fromisoformat(data_compra.replace('Z', '+00:00'))
                        else:
                            data_compra_obj = data_compra
                        proxima_acao = (data_compra_obj + timedelta(days=14)).isoformat()
                        update_client_next_action(client_id, proxima_acao)
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao calcular próxima ação: {e}")
                
                logger.info(f"✅ Cliente {client_nome} processado com sucesso")
            else:
                falhas += 1
                # Marca ação como falha
                update_action_result(acao_criada['id'], 'sem_resposta')
                logger.error(f"❌ Falha ao enviar mensagem para {client_nome}: {erro}")
        
        # 7. Resumo final
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

