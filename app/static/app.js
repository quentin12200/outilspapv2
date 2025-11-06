// Tu pourras ajouter des interactions HTMX ici si besoin.

// Plein écran pour le tableau principal
function toggleFullscreenTable(tableId) {
  let tbl = null;
  if (tableId) {
    tbl = document.getElementById(tableId);
  }
  if (!tbl) {
    tbl = document.querySelector('article > table, article section > table');
  }
  if (!tbl) return;

  // Trouver le conteneur scrollable parent (pour permettre le scroll vertical en plein écran)
  let container = tbl.closest('.table-scroll-container') || tbl.closest('.overflow-x-auto') || tbl.parentElement;

  if (!document.fullscreenElement) {
    // Mettre le conteneur en plein écran (pas juste la table)
    if (container && container.requestFullscreen) {
      container.requestFullscreen();
      // Ajouter une classe pour le style plein écran
      container.classList.add('fullscreen-active');
    }
  } else {
    document.exitFullscreen?.();
    // Retirer la classe au retour
    if (container) {
      container.classList.remove('fullscreen-active');
    }
  }
}

// Écouter les changements de mode plein écran (pour nettoyer quand on sort avec Escape)
document.addEventListener('fullscreenchange', function() {
  if (!document.fullscreenElement) {
    // On est sorti du mode plein écran
    const containers = document.querySelectorAll('.fullscreen-active');
    containers.forEach(container => {
      container.classList.remove('fullscreen-active');
    });
  }
});

window.toggleFullscreenTable = toggleFullscreenTable;

// Tri générique pour les tableaux
(function () {
  function getCellSortValue(cell) {
    if (!cell) {
      return '';
    }
    const explicit = cell.getAttribute('data-sort-value');
    if (explicit !== null) {
      return explicit;
    }
    return cell.textContent.trim();
  }

  function parseNumber(value) {
    if (value === null || value === undefined) {
      return NaN;
    }
    const normalized = value
      .toString()
      .trim()
      .replace(/\s+/g, '')
      .replace(',', '.');
    if (normalized === '') {
      return NaN;
    }
    return Number(normalized);
  }

  function detectColumnType(table, columnIndex, headerType) {
    if (headerType) {
      return headerType;
    }
    const rows = Array.from(table.tBodies?.[0]?.rows || []);
    for (const row of rows) {
      const cell = row.cells[columnIndex];
      if (!cell) continue;
      const value = getCellSortValue(cell);
      if (!value) continue;
      if (!Number.isNaN(Date.parse(value))) {
        return 'date';
      }
      if (!Number.isNaN(parseNumber(value))) {
        return 'numeric';
      }
      return 'string';
    }
    return 'string';
  }

  function compareValues(a, b, type) {
    if (type === 'numeric') {
      const aNum = parseNumber(a);
      const bNum = parseNumber(b);
      const aNaN = Number.isNaN(aNum);
      const bNaN = Number.isNaN(bNum);
      if (aNaN && bNaN) return 0;
      if (aNaN) return 1;
      if (bNaN) return -1;
      return aNum - bNum;
    }
    if (type === 'date') {
      const aTime = Date.parse(a);
      const bTime = Date.parse(b);
      const aNaN = Number.isNaN(aTime);
      const bNaN = Number.isNaN(bTime);
      if (aNaN && bNaN) return 0;
      if (aNaN) return 1;
      if (bNaN) return -1;
      return aTime - bTime;
    }
    const aStr = (a || '').toString().toLowerCase();
    const bStr = (b || '').toString().toLowerCase();
    return aStr.localeCompare(bStr, 'fr');
  }

  function clearSortIndicators(headers) {
    headers.forEach((header) => {
      header.removeAttribute('data-sort-direction');
      const indicator = header.querySelector('.sort-indicator');
      if (indicator) {
        indicator.textContent = '↕';
      }
    });
  }

  function applyRank(table) {
    const rankCells = table.querySelectorAll('tbody [data-rank-cell]');
    if (!rankCells.length) {
      return;
    }
    let index = 1;
    rankCells.forEach((cell) => {
      cell.textContent = `#${index}`;
      cell.setAttribute('data-sort-value', String(index));
      index += 1;
    });
  }

  function sortTable(table, columnIndex, direction, headerType) {
    const tbody = table.tBodies?.[0];
    if (!tbody) return;
    const rows = Array.from(tbody.rows);
    if (!rows.length) return;

    const type = detectColumnType(table, columnIndex, headerType);
    const multiplier = direction === 'desc' ? -1 : 1;

    rows.sort((rowA, rowB) => {
      const valueA = getCellSortValue(rowA.cells[columnIndex]);
      const valueB = getCellSortValue(rowB.cells[columnIndex]);
      return compareValues(valueA, valueB, type) * multiplier;
    });

    rows.forEach((row) => tbody.appendChild(row));
    applyRank(table);
  }

  function enhanceHeader(header) {
    if (header.dataset.enhanced === 'true') {
      return header;
    }
    header.dataset.enhanced = 'true';
    header.classList.add('sortable-header');

    const indicator = document.createElement('span');
    indicator.className = 'sort-indicator';
    indicator.textContent = '↕';
    header.appendChild(indicator);

    return header;
  }

  function initSortableTables() {
    const tables = document.querySelectorAll('table[data-sortable="true"]');
    tables.forEach((table) => {
      const headers = Array.from(table.querySelectorAll('thead th'));
      if (!headers.length) return;
      headers.forEach((header, index) => {
        enhanceHeader(header);
        header.addEventListener('click', () => {
          const currentDirection = header.getAttribute('data-sort-direction');
          const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
          clearSortIndicators(headers);
          header.setAttribute('data-sort-direction', newDirection);
          const indicator = header.querySelector('.sort-indicator');
          if (indicator) {
            indicator.textContent = newDirection === 'asc' ? '↑' : '↓';
          }
          sortTable(table, index, newDirection, header.dataset.sortType);
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSortableTables);
  } else {
    initSortableTables();
  }
})();
