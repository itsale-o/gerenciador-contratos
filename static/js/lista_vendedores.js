const btnNovo = document.getElementById("btnNovo");
const drawer = document.getElementById("drawer");
const overlay = document.getElementById("drawerOverlay");
const closeBtn = document.getElementById("closeDrawer");

btnNovo.addEventListener("click", () => {
    drawer.classList.add("active");
    overlay.classList.add("active");
});

closeBtn.addEventListener("click", closeDrawer);
overlay.addEventListener("click", closeDrawer);

function closeDrawer() {
    drawer.classList.remove("active");
    overlay.classList.remove("active");
}
