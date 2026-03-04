document.addEventListener("DOMContentLoaded", () => {
    const sidebar = document.querySelector("#sidebar");
    const hamburger = document.querySelector(".toggle-btn");
    const toggler = document.querySelector("#icon");

    const estadoMenu = localStorage.getItem("menuLateral");
    if (estadoMenu === "minimizado") {
        sidebar.classList.remove("expand");
        toggler.classList.remove("bi-chevron-double-left");
        toggler.classList.add("bi-chevron-double-right");
    } else {
        sidebar.classList.add("expand");
        toggler.classList.remove("bi-chevron-double-right");
        toggler.classList.add("bi-chevron-double-left");
    }

    hamburger.addEventListener("click", () => {
        const estaExpandido = sidebar.classList.toggle("expand");

        toggler.classList.toggle("bi-chevron-double-left", estaExpandido);
        toggler.classList.toggle("bi-chevron-double-right", !estaExpandido);

        localStorage.setItem("menuLateral", estaExpandido ? "expandido" : "minimizado");
    });
});
