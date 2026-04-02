document.addEventListener('DOMContentLoaded', function() {
   
    initializeDrilldown();
});


function initializeDrilldown() {
    const clickableCards = document.querySelectorAll('.card-clickable');
    
    if (clickableCards.length === 0) {
        return;
    }

    const modalElement = document.getElementById('drilldownModal');
    if (!modalElement) {
        return; 
    }

    const modal = new bootstrap.Modal(modalElement);
    const modalTitle = document.getElementById('drilldownTitle');
    const modalContent = document.getElementById('drilldownContent');

    const drilldownConfigs = {
        'leads-distribuicao': {
            title: 'Distribuição de Leads por Vendedor',
            url: '/api/dashboard/leads-distribuicao/'
        },
        'vendas-mes': {
            title: 'Vendas do Mês por Vendedor',
            url: '/api/dashboard/vendas-mes/'
        },
        'retornos-urgentes': {
            title: 'Detalhes de Retornos Urgentes',
            url: '/api/dashboard/retornos-urgentes/'
        },
        'leads-sem-contato': {
            title: 'Leads Sem Contato por Vendedor',
            url: '/api/dashboard/leads-sem-contato/'
        },
        'leads-com-contato': {
            title: 'Leads Com Contato por Vendedor',
            url: '/api/dashboard/leads-com-contato/'
        },
        'leads-sem-venda': {
            title: 'Leads Sem Venda (Contatados)',
            url: '/api/dashboard/leads-sem-venda/'
        },
        'leads-nao-venda': {
            title: 'Leads Não Convertidos',
            url: '/api/dashboard/leads-nao-venda/'
        },
        'leads-caro': {
            title: 'Leads que acharam caro',
            url: '/api/dashboard/leads-caro/'
        },
        'leads-sem-interesse': {
            title: 'Leads Sem Interesse',
            url: '/api/dashboard/leads-sem-interesse/'
        },
        'sessoes-ligacao': {
            title: 'Sessões de Ligação',
            url: '/api/dashboard/sessoes-ligacao/'
        },
        'tentativas-ligacao': {
            title: 'Tentativas de Ligação',
            url: '/api/dashboard/tentativas-ligacao/'
        },
        'vendedores-ativos': {
            title: 'Vendedores Ativos',
            url: '/api/dashboard/vendedores-ativos/'
        },
        'telefonia': {
            title: 'Telefonia - Detalhes de Chamadas',
            url: '/api/dashboard/telefonia/'
        }
    };

    clickableCards.forEach(card => {
        card.addEventListener('click', function() {
            const type = this.getAttribute('data-drilldown');
            const config = drilldownConfigs[type];

            if (config) {
                modalTitle.textContent = config.title;
                modalContent.innerHTML = `
                    <div class="text-center p-5">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Carregando...</span>
                        </div>
                        <p class="mt-2 text-muted">Buscando detalhes da equipe...</p>
                    </div>
                `;
                modal.show();

                fetch(config.url)
                    .then(response => {
                        if (!response.ok) {
                            return response.text().then(text => {
                                let message = `${response.status} ${response.statusText}`;
                                try {
                                    const json = JSON.parse(text);
                                    if (json && json.message) {
                                        message = json.message;
                                    }
                                } catch (err) {
                             
                                }
                                throw new Error(message);
                            });
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.status === 'success') {
                            renderDrilldownData(type, data.data);
                        } else {
                            modalContent.innerHTML = `<div class="alert alert-danger">Erro ao carregar dados: ${data.message}</div>`;
                        }
                    })
                    .catch(error => {
                        console.error('Erro:', error);
                        modalContent.innerHTML = `<div class="alert alert-danger">Erro ao carregar dados: ${error.message}</div>`;
                    });
            }
        });
    });

    function renderDrilldownData(type, data) {
        if (!data || data.length === 0) {
            modalContent.innerHTML = '<div class="alert alert-info">Nenhum dado encontrado para esta métrica.</div>';
            return;
        }

        if (type === 'vendedores-ativos') {
            let html = '<div class="drilldown-container">';
            html += '<div class="table-responsive">';
            html += '<table class="table table-sm table-hover">';
            html += '<thead><tr><th>Vendedor</th><th>Ramal</th><th>Leads</th><th>Status</th></tr></thead>';
            html += '<tbody>';
            data.forEach(item => {
                html += `
                    <tr>
                        <td>${escapeHtml(item.vendedor)}</td>
                        <td>${escapeHtml(item.ramal)}</td>
                        <td>${escapeHtml(item.total_leads)}</td>
                        <td><span class="badge ${getStatusBadge(item.status)}">${escapeHtml(item.status)}</span></td>
                    </tr>
                `;
            });
            html += '</tbody></table></div></div>';
            modalContent.innerHTML = html;
            return;
        }

        if (type === 'telefonia') {
            let html = '<div class="drilldown-container">';
            html += '<div class="table-responsive">';
            html += '<table class="table table-sm table-hover">';
            html += '<thead><tr>' +
                '<th>Vendedor</th>' +
                '<th>Total Chamadas</th>' +
                '<th>Atendidas</th>' +
                '<th>Não Atendidas</th>' +
                '<th>TMA</th>' +
                '<th>Tempo Total</th>' +
                '<th>Última Chamada</th>' +
                '</tr></thead>';
            html += '<tbody>';
            data.forEach(item => {
                html += `
                    <tr>
                        <td>${escapeHtml(item.vendedor_nome)}</td>
                        <td>${escapeHtml(item.total_chamadas)}</td>
                        <td>${escapeHtml(item.atendidas)}</td>
                        <td>${escapeHtml(item.nao_atendidas)}</td>
                        <td>${escapeHtml(item.tma)}</td>
                        <td>${escapeHtml(item.tempo_total)}</td>
                        <td>${escapeHtml(item.ultima_chamada)}</td>
                    </tr>
                `;
            });
            html += '</tbody></table></div></div>';
            modalContent.innerHTML = html;
            return;
        }

        let html = '<div class="drilldown-container">';

        data.forEach(item => {
            html += `
                <div class="vendedor-section">
                    <div class="vendedor-header d-flex justify-content-between align-items-center">
                        <h6 class="mb-0"><i class="bi bi-person-circle me-2"></i>${escapeHtml(item.vendedor)}</h6>
                        <span class="badge bg-primary">${getBadgeCount(type, item)}</span>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-sm table-hover table-drilldown-details">
                            <thead>
                                <tr>
                                    <th>Contrato</th>
                                    <th>Cliente</th>
                                    ${type === 'retornos-urgentes' ? '<th>Data Retorno</th>' : '<th>Valor</th>'}
                                    <th>Status</th>
                                    ${(type === 'leads-nao-venda' || type === 'leads-caro' || type === 'leads-sem-interesse') ? '<th>Ações</th>' : ''}
                                </tr>
                            </thead>
                            <tbody>
                                ${renderContratos(type, item.contratos)}
                            </tbody>
                        </table>
                        ${item.contratos.length >= 10 ? '<small class="text-muted ps-3">* Mostrando os 10 mais recentes</small>' : ''}
                    </div>
                </div>
            `;
        });

        html += '</div>';
        modalContent.innerHTML = html;
    }

    function renderContratos(type, contratos) {
        if (!contratos || contratos.length === 0) {
            return '<tr><td colspan="4" class="text-center text-muted">Nenhum contrato encontrado</td></tr>';
        }

        return contratos.map(c => `
            <tr>
                <td><strong>${escapeHtml(c.contrato)}</strong></td>
                <td>${escapeHtml(c.cliente)}</td>
                ${type === 'retornos-urgentes' ? 
                    `<td><span class="text-danger">${escapeHtml(c.proximo_contato)}</span></td>` : 
                    `<td>R$ ${formatarValor(c.valor)}</td>`
                }
                <td><span class="badge ${getStatusBadge(c.status)}">${escapeHtml(c.status)}</span></td>
                ${(window.isAdmin && ['leads-nao-venda', 'leads-caro', 'leads-sem-interesse'].includes(type)) ?
                    `<td><button class="btn btn-sm btn-outline-secondary" onclick="acionarReatribuir(${c.contrato})">Reatribuir</button></td>` :
                    ''
                }
            </tr>
        `).join('');
    }

    function getBadgeCount(type, item) {
        switch(type) {
            case 'leads-distribuicao': return `${item.total_leads} Leads`;
            case 'vendas-mes': return `${item.total_vendas} Vendas`;
            case 'retornos-urgentes': return `${item.total_retornos} Pendentes`;
            case 'leads-sem-contato': return `${item.total_sem_contato} Novos`;
            case 'leads-com-contato': return `${item.total_com_contato} Contatados`;
            case 'leads-sem-venda': return `${item.total_sem_venda} Perdas`;
            case 'leads-nao-venda': return `${item.total_nao_venda} Não venda`;
            case 'leads-caro': return `${item.total_caro} Caro`;
            case 'leads-sem-interesse': return `${item.total_sem_interesse} Sem interesse`;
            case 'sessoes-ligacao': return `${item.total_sessoes} Sessões`;
            case 'tentativas-ligacao': return `${item.total_tentativas} Tentativas`;
            case 'vendedores-ativos': return `${item.total_leads} Leads`;
            case 'telefonia': return `${item.total_chamadas} Chamadas`;
            default: return '';
        }
    }

    function getStatusBadge(status) {
        if (!status) return 'bg-secondary';
        const s = status.toUpperCase();
        if (s === 'ATIVO') return 'bg-success';
        if (s === 'CANCELADO') return 'bg-danger';
        if (s.includes('SUSPEN')) return 'bg-warning text-dark';
        return 'bg-info';
    }
}

function acionarReatribuir(contrato){
    const modal = new bootstrap.Modal(document.getElementById('reassignModal'));
    document.getElementById('reassignContratoId').value = contrato;

    const selectEl = document.getElementById('reassignVendedorId');
    selectEl.innerHTML = '<option value="">Carregando...</option>';

    fetch('/api/dashboard/vendedores-ativos/')
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') {
                alert('Não foi possível carregar vendedores.');
                return;
            }
            selectEl.innerHTML = '<option value="">Selecione o vendedor</option>' +
                data.data.map(v => `<option value="${v.id}">${v.vendedor} (ramal ${v.ramal})</option>`).join('');
            modal.show();
        })
        .catch(() => {
            alert('Erro ao carregar lista de vendedores.');
        });
}

function enviarReatribuir(){
    const contrato = document.getElementById('reassignContratoId').value;
    const vendedor_id = document.getElementById('reassignVendedorId').value;
    const obs = document.getElementById('reassignObservacao').value;

    if (!vendedor_id) {
        alert('Selecione um vendedor para reatribuir.');
        return;
    }

    const body = new URLSearchParams({
        contrato: contrato,
        vendedor_id: vendedor_id,
        observacao: obs,
    });

    fetch('/api/dashboard/reatribuir-lead/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: body
    })
    .then(r => r.json())
    .then(resp => {
        if(resp.status === 'success'){
            alert(resp.message);
            window.location.reload();
        } else {
            alert('Erro: ' + (resp.message || 'Falha ao reatribuir lead'));
        }
    })
    .catch(() => alert('Erro de rede ao reatribuir lead'));
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    text = String(text);
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function formatarValor(valor) {
    if (!valor) return '0,00';
    return parseFloat(valor).toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}
