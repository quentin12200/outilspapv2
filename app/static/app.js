// Tu pourras ajouter des interactions HTMX ici si besoin.

// Plein écran pour le tableau principal
function toggleFullscreenTable() {
  const tbl = document.querySelector('article > table, article section > table');
  if (!tbl) return;
  if (!document.fullscreenElement) {
    tbl.requestFullscreen();
  } else {
    document.exitFullscreen();
  }
}
window.toggleFullscreenTable = toggleFullscreenTable;
