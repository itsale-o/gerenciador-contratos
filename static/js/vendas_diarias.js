const btnSalvar = document.getElementById("btn-salvar");
const btnEditar = document.getElementById("btn-editar");
const data = document.getElementById("data").value;
const selectTurno = document.getElementById("turno");
const inputsVendedor = document.querySelectorAll(".input-volume, .input-receita");
let editando = false;

btnEditar.addEventListener("click", function () {
    const visualizacao = document.querySelectorAll(".modo-visualizacao");
    const edicao = document.querySelectorAll(".modo-edicao");

    btnSalvar.style.display = "block";
    editando = !editando

    visualizacao.forEach(el => {
        el.style.display = editando ? "none" : "inline";
    });

    edicao.forEach(el => {
        el.style.display = editando ? "block" : "none";
    });
});

btnSalvar.addEventListener("click", function () {
    let payload = [];
    const turno = selectTurno.value;

    inputsVendedor.forEach(input => {
        const vendedor = input.dataset.vendedor;
        const tipo = input.dataset.tipo;
        const valor = input.value ? parseFloat(input.value) : 0;

        const campo = input.classList.contains("input-volume") ? "volume" : "receita";
        payload.push({
            vendedor,
            tipo,
            campo,
            valor
        });
    });

    fetch("/salvar-vendas-dia/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken(),
        },
        body: JSON.stringify({
            data: data,
            turno: turno,
            itens: payload
        })
    })
    .then(res => res.json())
    .then(data => {
        sairModoEdicao();
        window.location.reload();
    });
});

function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function sairModoEdicao() {
    const itensVisualizacao = document.querySelectorAll(".modo-visualizacao");
    const modoEdicao = document.querySelectorAll(".modo-edicao");

    modoEdicao.forEach(el => el.style.display = "none");
    itensVisualizacao.forEach(el => el.style.display = "inline");
    btnSalvar.style.display = "none";
}


document.getElementById("btn-exportar").addEventListener("click", async () => {
    const elemento = document.getElementById("area-exportacao");
    elemento.classList.add("exportando");
    let nomeArquivo = "vendas_dia.png";

    if (data) {
        const [ano, mes, dia] = data.split("-");
        nomeArquivo = `vendas_${dia}_${mes}_${ano}.png`
    }

    await new Promise(resolve => setTimeout(resolve, 100));

    const canvas = await html2canvas(elemento, {
        backgroundColor: "#ffffff",
        scale: 3,
        useCORS: true
    });

    elemento.classList.remove("exportando");

    const link = document.createElement("a");

    link.download = nomeArquivo;
    link.href = canvas.toDataURL("image/png");

    link.click();

});