from datetime import date

from django.db.models import Case, Count, F, IntegerField, When
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.utils.timezone import now
from django.views.generic import View

from .mixins import GroupRequiredMixin
from .models import Lead, Vendedor
from .utils import fetch_claro_vendedor_estatisticas
from contratos.models import Contrato, AuditoriaCdr


class DashboardLeadsDistribuicaoAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            distribuicao = Lead.objects
            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                distribuicao = Lead.objects.filter(vendedor=vendedor)

            distribuicao = (
                distribuicao
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(
                    total=Count("id"),
                    com_contato=Count(
                        Case(When(contato_realizado=True, then=1), output_field=IntegerField())
                    ),
                    com_venda=Count(
                        Case(When(status="venda", then=1), output_field=IntegerField())
                    ),
                    sem_contato=Count(
                        Case(When(contato_realizado=False, then=1), output_field=IntegerField())
                    ),
                )
                .order_by("-total")
            )
            
            dados = []
            for item in distribuicao:
                vendedor_id = item["vendedor__id"]
                contratos_ids = list(
                    Lead.objects.filter(vendedor_id=vendedor_id)
                    .values_list("contrato_id", flat=True)
                )
                
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )[:10]
                
                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_leads": item["total"],
                    "com_contato": item["com_contato"],
                    "com_venda": item["com_venda"],
                    "sem_contato": item["sem_contato"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardVendasMesAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            hoje = now().date()
            inicio_mes = date(hoje.year, hoje.month, 1)
            
            lead_query = Lead.objects.filter(
                data_atribuicao__date__gte=inicio_mes,
                status="venda"
            )

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                lead_query = lead_query.filter(vendedor=vendedor)

            vendas_mes = (
                lead_query
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_vendas=Count("id"))
                .order_by("-total_vendas")
            )
            
            dados = []
            for venda in vendas_mes:
                vendedor_id = venda["vendedor__id"]
                leads_venda = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    data_atribuicao__date__gte=inicio_mes,
                    status_contato="venda"
                )
                
                contratos_ids = [lead.contrato_id for lead in leads_venda]
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )
                
                dados.append({
                    "vendedor": venda["vendedor__usuario__username"],
                    "total_vendas": venda["total_vendas"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardRetornosUrgentesAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            agora = now()
            
            lead_query = Lead.objects.filter(
                proximo_contato__lte=agora,
                resolvido=False
            )

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                lead_query = lead_query.filter(vendedor=vendedor)

            retornos = (
                lead_query
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_retornos=Count("id"))
                .order_by("-total_retornos")
            )
            
            dados = []
            for retorno in retornos:
                vendedor_id = retorno["vendedor__id"]
                leads_retorno = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    proximo_contato__lte=agora,
                    resolvido=False
                ).order_by("proximo_contato")
                
                contratos_info = []
                for lead in leads_retorno[:10]:
                    contrato = Contrato.objects.filter(contrato=lead.contrato_id).first()
                    if contrato:
                        contratos_info.append({
                            "contrato": contrato.contrato,
                            "cliente": contrato.nome,
                            "proximo_contato": lead.proximo_contato.strftime("%d/%m/%Y %H:%M"),
                            "observacao": lead.observacao or "Sem observações",
                        })
                
                dados.append({
                    "vendedor": retorno["vendedor__usuario__username"],
                    "total_retornos": retorno["total_retornos"],
                    "contratos": contratos_info,
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardSessoesLigacaoAPI(GroupRequiredMixin, View):
    """API para obter sessões de ligação por vendedor"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            sessoes = AuditoriaCdr.objects

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                sessoes = sessoes.filter(vendedor_id=vendedor.usuario_id)

            sessoes = (
                sessoes
                .values("vendedor_nome", "vendedor_id")
                .annotate(total_sessoes=Count("contrato_numero", distinct=True))
                .order_by("-total_sessoes")
            )

            dados = []
            for item in sessoes:
                vendedor_id = item["vendedor_id"]
                sessoes_leads = (
                    AuditoriaCdr.objects.filter(vendedor_id=vendedor_id)
                    .values('contrato_numero', 'contrato_nome', 'inicio')
                    .distinct()
                    .order_by("-inicio")[:10]
                )

                contratos_info = []
                for sessao in sessoes_leads:
                    contratos_info.append({
                        "contrato": sessao['contrato_numero'],
                        "cliente": sessao['contrato_nome'],
                        "valor": None,  # Não temos valor na auditoria_cdr
                        "status": None,  # Não temos status na auditoria_cdr
                        "proximo_contato": sessao['inicio'].strftime("%d/%m/%Y %H:%M") if sessao['inicio'] else "",
                    })

                dados.append({
                    "vendedor": item["vendedor_nome"],
                    "total_sessoes": item["total_sessoes"],
                    "contratos": contratos_info
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardTentativasLigacaoAPI(GroupRequiredMixin, View):
    """API para obter tentativas de ligação por vendedor"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            tentativas = AuditoriaCdr.objects

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                tentativas = tentativas.filter(vendedor_id=vendedor.usuario_id)

            tentativas_agg = (
                tentativas
                .values("vendedor_nome", "vendedor_id")
                .annotate(total_tentativas=Count("uuid"))
                .order_by("-total_tentativas")
            )

            dados = []
            for item in tentativas_agg:
                vendedor_id = item["vendedor_id"]
                tentativas_vendedor = (
                    AuditoriaCdr.objects.filter(vendedor_id=vendedor_id)
                    .order_by("-inicio")[:10]
                )

                contratos_info = []
                for tentativa in tentativas_vendedor:
                    contratos_info.append({
                        "contrato": tentativa.contrato_numero,
                        "cliente": tentativa.contrato_nome,
                        "valor": None,  # Não temos valor na auditoria_cdr
                        "status": None,  # Não temos status na auditoria_cdr
                        "proximo_contato": tentativa.inicio.strftime("%d/%m/%Y %H:%M") if tentativa.inicio else "",
                    })

                dados.append({
                    "vendedor": item["vendedor_nome"],
                    "total_tentativas": item["total_tentativas"],
                    "contratos": contratos_info
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardTelefoniaAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            vendedores = fetch_claro_vendedor_estatisticas()
            dados = []

            for item in vendedores:
                dados.append({
                    "vendedor_id": item.get("vendedor_id"),
                    "vendedor_nome": item.get("vendedor_nome"),
                    "total_chamadas": item.get("total_chamadas", 0),
                    "atendidas": item.get("atendidas", 0),
                    "nao_atendidas": item.get("nao_atendidas", 0),
                    "tma": item.get("tma", "00:00:00"),
                    "tempo_total": item.get("tempo_total", 0),
                    "ultima_chamada": item.get("ultima_chamada", ""),
                    "tma_segundos": item.get("tma_segundos", 0),
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardLeadsSemContatoAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            sem_contato = (
                Lead.objects
                .filter(contato_realizado=False)
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_sem_contato=Count("id"))
                .order_by("-total_sem_contato")
            )
            
            dados = []
            for item in sem_contato:
                vendedor_id = item["vendedor__id"]
                leads_sem_contato = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    contato_realizado=False
                )
                
                contratos_ids = [lead.contrato_id for lead in leads_sem_contato]
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )[:10]
                
                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_sem_contato": item["total_sem_contato"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardLeadsComContatoAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            com_contato = (
                Lead.objects
                .filter(contato_realizado=True)
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_com_contato=Count("id"))
                .order_by("-total_com_contato")
            )
            
            dados = []
            for item in com_contato:
                vendedor_id = item["vendedor__id"]
                leads_com_contato = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    contato_realizado=True
                )
                
                contratos_ids = [lead.contrato_id for lead in leads_com_contato]
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )[:10]
                
                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_com_contato": item["total_com_contato"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardLeadsSemVendaAPI(GroupRequiredMixin, View):
    """API para obter detalhes de leads sem venda por vendedor"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            sem_venda = (
                Lead.objects
                .filter(
                    contato_realizado=True,
                    status_contato__isnull=True
                )
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_sem_venda=Count("id"))
                .order_by("-total_sem_venda")
            )
            
            dados = []
            for item in sem_venda:
                vendedor_id = item["vendedor__id"]
                leads_sem_venda = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    contato_realizado=True,
                    status_contato__isnull=True
                )
                
                contratos_ids = [lead.contrato_id for lead in leads_sem_venda]
                contratos = (
                    Contrato.objects
                    .filter(contrato__in=contratos_ids)
                    .annotate(cliente=F("nome"))
                    .values("contrato", "cliente", "valor", "status")
                )[:10]
                
                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_sem_venda": item["total_sem_venda"],
                    "contratos": list(contratos),
                })
            
            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardLeadsNaoVendaAPI(GroupRequiredMixin, View):
    """API para obter leads que não viraram venda"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            leads = Lead.objects.filter(contato_realizado=True).exclude(status_contato__in=["venda", "nao_atendeu", "ligar_mais_tarde"])

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                leads = leads.filter(vendedor=vendedor)

            nao_venda = (
                leads
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_nao_venda=Count("id"))
                .order_by("-total_nao_venda")
            )

            dados = []
            for item in nao_venda:
                vendedor_id = item["vendedor__id"]
                leads_vendedor = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    contato_realizado=True
                ).exclude(status_contato__in=["venda", "nao_atendeu", "ligar_mais_tarde"])

                contratos_info = []
                for lead in leads_vendedor[:10]:
                    contrato = Contrato.objects.filter(contrato=lead.contrato_id).first()
                    if contrato:
                        contratos_info.append({
                            "contrato": contrato.contrato,
                            "cliente": contrato.nome,
                            "valor": contrato.valor,
                            "status": contrato.status,
                            "status_contato": lead.status_contato,
                        })

                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_nao_venda": item["total_nao_venda"],
                    "contratos": contratos_info,
                })

            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)


class DashboardLeadsCaroAPI(GroupRequiredMixin, View):
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            leads = Lead.objects.filter(status_contato="caro")

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                leads = leads.filter(vendedor=vendedor)

            leads_caro = (
                leads
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_caro=Count("id"))
                .order_by("-total_caro")
            )

            dados = []
            for item in leads_caro:
                vendedor_id = item["vendedor__id"]
                leads_vendedor = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    status_contato="caro"
                )

                contratos_info = []
                for lead in leads_vendedor[:10]:
                    contrato = Contrato.objects.filter(contrato=lead.contrato_id).first()
                    if contrato:
                        contratos_info.append({
                            "contrato": contrato.contrato,
                            "cliente": contrato.nome,
                            "valor": contrato.valor,
                            "status": contrato.status,
                            "status_contato": lead.status_contato,
                        })

                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_caro": item["total_caro"],
                    "contratos": contratos_info,
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardLeadsSemInteresseAPI(GroupRequiredMixin, View):
    """API para obter leads que não tem interesse"""
    groups_required = ["Admin", "Vendedor"]
    return_json = True

    def get(self, request):
        try:
            leads = Lead.objects.filter(status_contato="sem_interesse")

            if request.user.groups.filter(name="Vendedor").exists():
                vendedor = Vendedor.objects.get(usuario=request.user)
                leads = leads.filter(vendedor=vendedor)

            leads_sem_interesse = (
                leads
                .values("vendedor__usuario__username", "vendedor__id")
                .annotate(total_sem_interesse=Count("id"))
                .order_by("-total_sem_interesse")
            )

            dados = []
            for item in leads_sem_interesse:
                vendedor_id = item["vendedor__id"]
                leads_vendedor = Lead.objects.filter(
                    vendedor_id=vendedor_id,
                    status_contato="sem_interesse"
                )

                contratos_info = []
                for lead in leads_vendedor[:10]:
                    contrato = Contrato.objects.filter(contrato=lead.contrato_id).first()
                    if contrato:
                        contratos_info.append({
                            "contrato": contrato.contrato,
                            "cliente": contrato.nome,
                            "valor": contrato.valor,
                            "status": contrato.status,
                            "status_contato": lead.status_contato,
                        })

                dados.append({
                    "vendedor": item["vendedor__usuario__username"],
                    "total_sem_interesse": item["total_sem_interesse"],
                    "contratos": contratos_info,
                })

            return JsonResponse({"status": "success", "data": dados})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


@method_decorator(require_POST, name="dispatch")
class DashboardReatribuirLeadAPI(GroupRequiredMixin, View):
    """API para reatribuir lead a outro vendedor"""

    groups_required = ["Admin"]
    return_json = True

    def post(self, request):
        contrato_id = request.POST.get("contrato")
        vendedor_id = request.POST.get("vendedor_id")
        observacao = request.POST.get("observacao", "").strip()

        if not contrato_id or not vendedor_id:
            return JsonResponse({"status": "error", "message": "Dados incompletos."}, status=400)

        try:
            lead = Lead.objects.filter(contrato_id=contrato_id).first()
            vendedor_destino = Vendedor.objects.get(id=vendedor_id)

            if not lead:
                return JsonResponse({"status": "error", "message": "Lead não encontrado."}, status=404)

            if lead.status_contato in ["venda", "nao_atendeu", "ligar_mais_tarde"]:
                return JsonResponse({"status": "error", "message": "Este lead não pode ser reatribuído neste momento."}, status=400)

            observacao_final = f"Reatribuído para {vendedor_destino.usuario.username} por {request.user.username}"
            if observacao:
                observacao_final += f" - Motivo: {observacao}"

            if lead.observacao:
                lead.observacao = f"{lead.observacao} | {observacao_final}"
            else:
                lead.observacao = observacao_final

            lead.vendedor = vendedor_destino
            lead.contato_realizado = False
            lead.status_contato = None
            lead.resolvido = False
            lead.resolvido_em = None
            lead.save(update_fields=["vendedor", "observacao", "contato_realizado", "status_contato", "resolvido", "resolvido_em"])

            return JsonResponse({"status": "success", "message": "Lead reatribuído com sucesso."})
        except Vendedor.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Vendedor destino inválido."}, status=404)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)


class DashboardVendedoresAtivosAPI(GroupRequiredMixin, View):
    """API para obter lista de vendedores ativos"""
    groups_required = ["Admin"]
    return_json = True

    def get(self, request):
        try:
            vendedores = (
                Vendedor.objects
                .filter(status="ativo")
                .annotate(total_leads=Count("leads"))
                .select_related("usuario")
                .order_by("usuario__username")
            )

            dados = [
                {
                    "id": v.id,
                    "vendedor": v.usuario.username,
                    "ramal": v.ramal,
                    "total_leads": v.total_leads,
                    "status": v.status,
                }
                for v in vendedores
            ]

            return JsonResponse({
                "status": "success",
                "data": dados,
            })
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)

