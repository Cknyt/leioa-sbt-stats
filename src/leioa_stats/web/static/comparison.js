// Cambia el equipo con el que se compara (comparativa.html). Los datos de todos los equipos
// van en la propia página (#teams-data), así que no hace falta pedir nada al servidor.
// También se puede abrir con un equipo elegido: comparativa.html#<equipo>.
(function () {
  "use strict";
  var source = document.getElementById("teams-data");
  var picker = document.getElementById("rival-picker");
  if (!source || !picker) return;
  var teams = JSON.parse(source.textContent);
  var rows = document.querySelectorAll("table.compare tr[data-direction]");
  var own = null;
  // El equipo propio es el único que no está en el desplegable.
  Object.keys(teams).forEach(function (key) {
    if (!picker.querySelector('option[value="' + key + '"]')) own = teams[key];
  });
  picker.parentElement.hidden = false;

  function show(key) {
    var rival = teams[key];
    if (!rival || !own) return;
    document.getElementById("rival-name").textContent = rival.name;
    document.getElementById("rival-meta").textContent = rival.games + " PJ · " + rival.record;
    document.getElementById("rival-link").href = "equipos/" + key + ".html";
    document.getElementById("rival-link-name").textContent = rival.name;
    Array.prototype.forEach.call(rows, function (row, i) {
      var cell = row.querySelector("td.rival");
      cell.textContent = rival.values[i] + " ";
      var rank = document.createElement("small");
      rank.textContent = rival.ranks[i] + "º";
      cell.appendChild(rank);
      // Misma regla que better() en build.py.
      var direction = Number(row.dataset.direction);
      var a = own.raw[i], b = rival.raw[i];
      var winner = direction === 0 || a === null || b === null || a === b
        ? null : (a - b) * direction > 0 ? "own" : "other";
      row.cells[1].classList.toggle("better", winner === "own");
      cell.classList.toggle("better", winner === "other");
    });
  }

  picker.addEventListener("change", function () {
    show(picker.value);
    history.replaceState(null, "", "#" + picker.value);
  });
  function fromHash() {
    var hash = location.hash.slice(1);
    if (teams[hash] && teams[hash] !== own) {
      picker.value = hash;
      show(hash);
    }
  }
  window.addEventListener("hashchange", fromHash);
  fromHash();
})();
