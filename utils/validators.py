"""
Utilitários de validação para dados de clientes.
"""
import re
from typing import Tuple, Optional


def validate_phone(telefone: str) -> Tuple[bool, Optional[str]]:
    """
    Valida formato de telefone brasileiro.
    
    Aceita formatos:
    - (11) 98765-4321
    - 11 98765-4321
    - 11987654321
    - +55 11 98765-4321
    
    Args:
        telefone: String com o número de telefone
    
    Returns:
        Tuple[bool, Optional[str]]: (é_válido, mensagem_de_erro)
    """
    if not telefone:
        return False, "Telefone não pode ser vazio"
    
    # Remove caracteres não numéricos (exceto + no início)
    telefone_limpo = re.sub(r'[^\d+]', '', telefone)
    
    # Remove o + se existir
    if telefone_limpo.startswith('+'):
        telefone_limpo = telefone_limpo[1:]
    
    # Remove código do país se existir (55 para Brasil)
    if telefone_limpo.startswith('55'):
        telefone_limpo = telefone_limpo[2:]
    
    # Valida comprimento (DDD + número)
    # DDD: 2 dígitos, Celular: 9 dígitos (começando com 9)
    # Fixo: 8 dígitos
    if len(telefone_limpo) < 10 or len(telefone_limpo) > 11:
        return False, f"Telefone deve ter entre 10 e 11 dígitos (com DDD). Recebido: {len(telefone_limpo)} dígitos"
    
    # Valida DDD (deve estar entre 11 e 99)
    ddd = telefone_limpo[:2]
    if not ddd.isdigit() or int(ddd) < 11 or int(ddd) > 99:
        return False, f"DDD inválido: {ddd}"
    
    # Valida se é celular (9 dígitos após DDD) ou fixo (8 dígitos)
    numero = telefone_limpo[2:]
    if len(numero) == 9:
        # Celular deve começar com 9
        if not numero.startswith('9'):
            return False, "Número de celular deve começar com 9"
    elif len(numero) == 8:
        # Fixo não deve começar com 0 ou 1
        if numero.startswith('0') or numero.startswith('1'):
            return False, "Número fixo inválido"
    else:
        return False, "Número deve ter 8 (fixo) ou 9 (celular) dígitos após o DDD"
    
    return True, None


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Valida formato de email.
    
    Args:
        email: String com o endereço de email
    
    Returns:
        Tuple[bool, Optional[str]]: (é_válido, mensagem_de_erro)
    """
    if not email:
        return True, None  # Email é opcional
    
    # Regex básico para validação de email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False, "Formato de email inválido"
    
    # Validações adicionais
    if len(email) > 254:  # Limite RFC 5321
        return False, "Email muito longo (máximo 254 caracteres)"
    
    if email.count('@') != 1:
        return False, "Email deve conter exatamente um @"
    
    # Verifica se não começa ou termina com ponto
    if email.startswith('.') or email.endswith('.'):
        return False, "Email não pode começar ou terminar com ponto"
    
    return True, None


def sanitize_phone(telefone: str) -> str:
    """
    Sanitiza telefone removendo caracteres especiais e formatando.
    
    Args:
        telefone: String com o número de telefone
    
    Returns:
        String com telefone limpo (apenas dígitos)
    """
    # Remove tudo exceto dígitos
    telefone_limpo = re.sub(r'\D', '', telefone)
    
    # Remove código do país se existir
    if telefone_limpo.startswith('55') and len(telefone_limpo) > 11:
        telefone_limpo = telefone_limpo[2:]
    
    return telefone_limpo


def sanitize_email(email: str) -> str:
    """
    Sanitiza email removendo espaços e convertendo para minúsculas.
    
    Args:
        email: String com o endereço de email
    
    Returns:
        String com email sanitizado
    """
    if not email:
        return ""
    
    # Remove espaços e converte para minúsculas
    email_limpo = email.strip().lower()
    
    return email_limpo


def sanitize_cpf(cpf: str) -> str:
    """Remove caracteres não numéricos do CPF e retorna string com 11 dígitos quando possível."""
    if not cpf:
        return ""
    cpf_digits = re.sub(r'\D', '', cpf)
    return cpf_digits


def validate_cpf(cpf: str) -> Tuple[bool, Optional[str]]:
    """Valida CPF (formato e dígitos verificadores).

    Retorna (True, None) se válido, senão (False, mensagem).
    """
    if not cpf:
        return False, "CPF não pode ser vazio"
    cpf_digits = sanitize_cpf(cpf)
    if len(cpf_digits) != 11:
        return False, "CPF deve ter 11 dígitos"
    # Elimina CPFs com todos dígitos iguais
    if cpf_digits == cpf_digits[0] * 11:
        return False, "CPF inválido"

    def calc_digit(digs):
        s = sum(int(d) * w for d, w in zip(digs, range(len(digs)+1, 1, -1)))
        r = (s * 10) % 11
        return '0' if r == 10 else str(r)

    first9 = cpf_digits[:9]
    d1 = calc_digit(first9)
    d2 = calc_digit(first9 + d1)
    if cpf_digits[-2:] != d1 + d2:
        return False, "CPF inválido"
    return True, None

