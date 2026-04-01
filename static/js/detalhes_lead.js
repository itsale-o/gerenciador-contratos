const botaoLigar = document.querySelectorAll(".btn-ligar");

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
            document.getElementById("ligacao-status").textContent = "Erro";
            document.getElementById("ligacao-subtexto").textContent = data.erro || "Não foi possível iniciar a ligação.";
            console.error(data.erro || "Erro ao iniciar ligação.");
            return;
        }

        acompanharEventos(data.uuid);
    } catch (error) {
        console.error("Erro ao iniciar ligação:", error);
        document.getElementById("ligacao-status").textContent = "Erro";
        document.getElementById("ligacao-subtexto").textContent = "Falha na comunicação com o servidor.";
    }
}

function acompanharEventos(uuid) {
    console.log("Iniciando polling. UUID:", uuid);

    let intervaloMs = 1000;
    let pollingId = null;
    let contador = 0;

    async function consultar() {
        try {
            contador++;

            const response = await fetch(`/comms/acompanhar-chamada/?uuid=${uuid}`);
            const data = await response.json();

            console.log("Retorno acompanhar-chamada:", data);

            if (!response.ok) {
                console.error(data.erro || "Erro ao consultar chamada.");
                clearInterval(pollingId);
                atualizarDisplayLigacao("ERRO");
                return;
            }

            if (data.ultimo_evento) {
                console.log("Último evento:", data.ultimo_evento);
                atualizarDisplayLigacao(data.ultimo_evento);
            }

            if (data.finalizada) {
                console.log("Chamada finalizada.");
                clearInterval(pollingId);
                return;
            }

            // depois de 15 consultas (~15s), muda para 5s
            if (contador === 15) {
                clearInterval(pollingId);
                intervaloMs = 5000;
                pollingId = setInterval(consultar, intervaloMs);
                console.log("Polling alterado para 5 segundos.");
            }

        } catch (error) {
            console.error("Erro no polling:", error);
            clearInterval(pollingId);
            atualizarDisplayLigacao("ERRO");
        }
    }

    pollingId = setInterval(consultar, intervaloMs);
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

function traduzirEvento(evento) {
    const mapa = {
        "CHAMANDO_DESTINO": {
            status: "Chamando...",
            subtexto: "Aguardando atendimento"
        },
        "AGENTE_ATENDEU": {
            status: "Conectando...",
            subtexto: "Ramal atendeu"
        },
        "INICIO": {
            status: "Em ligação",
            subtexto: "Chamada em andamento"
        },
        "AGENTE_HANGUP": {
            status: "Ligação encerrada",
            subtexto: "Encerrada pelo vendedor"
        },
        "FIM": {
            status: "Finalizada",
            subtexto: "Chamada concluída"
        }
    };

    return mapa[evento] || {
        statud: evento,
        subtexto: "Atualizando status..."
    }
}

function atualizarDisplayLigacao(evento) {
    const statusEl = document.getElementById("ligacao-status");
    const subtextoEl = document.getElementById("ligacao-subtexto");

    const traduzido = traduzirEvento(evento);

    statusEl.textContent = traduzido.status;
    subtextoEl.textContent = traduzido.subtexto;
}