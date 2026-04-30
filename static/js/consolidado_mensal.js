const btnEditar = document.getElementById("btn-editar");
const btnSalvar = document.getElementById("btn-salvar");
const anoAtual = parseInt(document.getElementById("ano").value);
const mesAtual = parseInt(document.getElementById("mes").value);

let editando = false;

btnEditar.addEventListener('click', function () {
    const views = document.querySelectorAll('.modo-visualizacao');
    const edits = document.querySelectorAll('.modo-edicao');

    btnSalvar.style.display = "block";
    editando = !editando;

    views.forEach(el => {
        el.style.display = editando ? 'none' : 'inline';
    });

    edits.forEach(el => {
        el.style.display = editando ? 'block' : 'none';
    });
});

btnSalvar.addEventListener("click", function () {
    salvarMetas();
});

function salvarMetas() {
    const inputsMeta = document.querySelectorAll(".input-meta");

    let payload = [];

    inputsMeta.forEach(input => {
        payload.push({
            vendedor: input.dataset.vendedor,
            valor: parseFloat(input.value) || 0
        });
    });

    btnSalvar.disabled = true;
    btnSalvar.innerText = "Salvando...";

    fetch('/salvar-meta-receita/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify({
            ano: anoAtual,
            mes: mesAtual,
            metas: payload
        })
    })
    .then(res => {
        if (!res.ok) throw new Error("Erro na requisição");
        return res.json();
    })
    .then(() => {
        window.location.reload();
    })
    .catch(() => {
        alert("Erro ao salvar");
        btnSalvar.disabled = false;
        btnSalvar.innerText = "Salvar";
    });
}

function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function sairModoEdicao() {
    const itensVisualizacao = document.querySelectorAll(".modo-visualizacao");
    const modoEdicao = document.querySelectorAll(".modo-edicao");

    modoEdicao.forEach(el => el.style.display = "none");
    itensVisualizacao.forEach(el => el.style.display = "inline");

    btnSalvar.style.display = "none";

    editando = false;
}