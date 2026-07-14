from app.models.funcao import Funcao
from app.models.usuario import Usuario
from app.models.usuario_cliente import UsuarioCliente
from app.models.setor import Setor
from app.models.categoria import Categoria
from app.models.marca import Marca
from app.models.grupo import Grupo
from app.models.equipamento import Equipamento
from app.models.cliente import Cliente
from app.models.funcionario import Funcionario
from app.models.equipamento_cliente import EquipamentoCliente
from app.models.historico_equipamento import HistoricoEquipamento
from app.models.fase import Fase
from app.models.log_os import LogOS
from app.models.ordem import Ordem
from app.models.tipo_calibragem import TipoCalibragem
from app.models.solicitacao import Solicitacao
from app.models.foto import Foto
from app.models.caixa import Caixa
from app.models.certificado_modelo import CertificadoModelo
from app.models.certificado_imagem import CertificadoImagem
from app.models.os_certificado import OSCertificado
from app.models.transferencia_equipamento import TransferenciaEquipamento
from app.models.certificado_avulso import CertificadoAvulso

__all__ = [
    "Funcao", "Usuario", "UsuarioCliente", "Setor", "Categoria",
    "Marca", "Grupo", "Equipamento", "Cliente", "Funcionario",
    "EquipamentoCliente", "HistoricoEquipamento",
    "Fase", "LogOS", "Ordem", "TipoCalibragem", "Solicitacao", "Foto",
    "Caixa", "CertificadoModelo", "CertificadoImagem", "OSCertificado",
    "TransferenciaEquipamento", "CertificadoAvulso",
]
