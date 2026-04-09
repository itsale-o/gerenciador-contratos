const botaoLigar = document.querySelectorAll(".btn-ligar");
let pollingTimeoutId = null;
let pollingAtivo = false;
let pollingTokenAtual = 0;


function getCSRFToken() {
    const name = "csrftoken=";
    const cookies = document.cookie.split(";");

    for (let cookie of cookies) {
        cookie = cookie.trim();

        if (cookie.startsWith(name)) {
            return cookie.substring(name.length, cookie.length);
        }
    }

    return "";
}

async function iniciarLigacao(contratoId, telefoneRaw, telefoneFormatado) {
    console.log("Iniciando ligação...", { contratoId, telefoneRaw, telefoneFormatado });

    abrirModalLigacao(telefoneFormatado);

    const body = new URLSearchParams({ telefone: telefoneRaw });

    try {
        const response = await fetch(`/comms/contatar-cliente/${contratoId}/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCSRFToken(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body
        });

        const data = await response.json();
        console.log("Resposta de contatar-cliente:", data);

        if (!response.ok) {
            atualizarDisplayErro(data.erro || "Não foi possível iniciar a ligação.");
            return;
        }

        if (!data.call_id) {
            atualizarDisplayErro("A chamada foi iniciada, mas nenhum identificador foi retornado.");
            return;
        }

        atualizarDisplayLigacao({
            estado: data.estado_inicial || "queued",
            status_raw: "",
            mensagem: "Ligação iniciada"
        });

        acompanharChamada(data.call_id);
    } catch (error) {
        console.error("Erro ao iniciar ligação:", error);
        atualizarDisplayErro("Falha na comunicação com o servidor.");
    }
}

function acompanharChamada(callId) {
    console.log("Iniciando polling. CALL ID:", callId);

    // invalida qualquer polling anterior
    pollingTokenAtual++;
    const meuToken = pollingTokenAtual;

    pararPolling();
    pollingAtivo = true;

    let contador = 0;

    async function consultar() {
        // se esse polling já foi substituído por outro, aborta
        if (!pollingAtivo || meuToken !== pollingTokenAtual) {
            return;
        }

        try {
            contador++;

            const response = await fetch(
                `/comms/acompanhar-chamada/?id=${encodeURIComponent(callId)}`,
                { cache: "no-store" }
            );

            const data = await response.json();

            // se esse polling ficou velho enquanto aguardava a resposta, ignora
            if (!pollingAtivo || meuToken !== pollingTokenAtual) {
                return;
            }

            console.log("Retorno acompanhar-chamada:", data);

            if (!response.ok) {
                console.error(data.erro || "Erro ao consultar chamada.");
                pararPolling();
                atualizarDisplayErro(data.erro || "Erro ao consultar chamada.");
                return;
            }

            atualizarDisplayLigacao(data);

            if (chamadaFinalizada(data)) {
                console.log("Chamada finalizada.");
                pararPolling();
                return;
            }

            const proximoIntervalo = contador >= 15 ? 5000 : 1000;

            pollingTimeoutId = setTimeout(() => {
                consultar();
            }, proximoIntervalo);

        } catch (error) {
            if (!pollingAtivo || meuToken !== pollingTokenAtual) {
                return;
            }

            console.error("Erro no polling:", error);
            pararPolling();
            atualizarDisplayErro("Erro ao acompanhar a chamada.");
        }
    }

    consultar();
}

botaoLigar.forEach(function (botao) {
    botao.addEventListener("click", function () {
        const contratoId = this.dataset.contrato;
        const telefone = this.dataset.telefoneRaw;
        const telefoneFormatado = this.dataset.telefoneFormatado;

        console.log("Botão de ligação clicado");
        iniciarLigacao(contratoId, telefone, telefoneFormatado);
    });
});

function abrirModalLigacao(telefoneFormatado) {
    const statusEl = document.getElementById("ligacao-status");
    const numeroEl = document.getElementById("ligacao-numero");
    const subtextoEl = document.getElementById("ligacao-subtexto");

    statusEl.textContent = "Chamando...";
    numeroEl.textContent = telefoneFormatado || "-";
    subtextoEl.textContent = "Iniciando chamada";

    const modalElement = document.getElementById("modalLigacao");
    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

function traduzirStatusChamada(data) {
    const estado = (data.estado || "").toLowerCase();
    const statusRaw = (data.status_raw || "").trim().toLowerCase();
    const aguardandoRetry = Boolean(data.aguardando_retry);

    if (estado === "finished") {
        if (statusRaw === "completed") {
            return {
                status: "Finalizada",
                subtexto: "Chamada concluída com sucesso"
            };
        }

        if (statusRaw === "busy") {
            return {
                status: "Finalizada",
                subtexto: "Número ocupado"
            };
        }

        if (statusRaw === "no answer") {
            return {
                status: "Finalizada",
                subtexto: "Não atendeu"
            };
        }

        if (statusRaw === "failed") {
            return {
                status: "Falha",
                subtexto: "Não foi possível completar a chamada"
            };
        }

        return {
            status: "Finalizada",
            subtexto: data.mensagem || "Chamada encerrada"
        };
    }

    if (aguardandoRetry) {
        return {
            status: "Tentando novamente...",
            subtexto: "Aguardando nova tentativa do sistema"
        };
    }

    if (estado === "queued") {
        return {
            status: "Chamando...",
            subtexto: "Ligação colocada na fila"
        };
    }

    if (estado === "calling" || estado === "ringing") {
        return {
            status: "Chamando...",
            subtexto: "Aguardando atendimento"
        };
    }

    if (estado === "in_call" || estado === "connected" || estado === "up") {
        return {
            status: "Em ligação",
            subtexto: "Chamada em andamento"
        };
    }

    return {
        status: "Atualizando...",
        subtexto: data.mensagem || "Consultando status da chamada"
    };
}

function atualizarDisplayLigacao(data) {
    const statusEl = document.getElementById("ligacao-status");
    const subtextoEl = document.getElementById("ligacao-subtexto");

    const traduzido = traduzirStatusChamada(data);

    statusEl.textContent = traduzido.status;
    subtextoEl.textContent = traduzido.subtexto;
}

function atualizarDisplayErro(mensagem) {
    const statusEl = document.getElementById("ligacao-status");
    const subtextoEl = document.getElementById("ligacao-subtexto");

    statusEl.textContent = "Erro";
    subtextoEl.textContent = mensagem || "Ocorreu um erro inesperado.";
}

function chamadaFinalizada(data) {
    const estado = (data.estado || "").trim().toLowerCase();
    const statusRaw = (data.status_raw || "").trim().toLowerCase();
    const local = (data.local || "").trim().toLowerCase();

    return (
        data.finalizada === true ||
        estado === "finished" ||
        ["completed", "busy", "no answer", "failed", "cancelled", "canceled"].includes(statusRaw) ||
        local === "outgoing_done"
    );
}

function pararPolling() {
    pollingAtivo = false;

    if (pollingTimeoutId) {
        clearTimeout(pollingTimeoutId);
        pollingTimeoutId = null;
    }
}