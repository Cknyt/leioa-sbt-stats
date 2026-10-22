// Ordena las tarjetas de jugadores (jugadores.html) por minutos, puntos, acierto o uso.
// Sin JavaScript, las tarjetas quedan ordenadas por minutos y los botones no se muestran.
(function () {
  "use strict";
  var sorter = document.querySelector(".sorter");
  var list = document.querySelector(".player-cards");
  if (!sorter || !list) return;
  sorter.hidden = false;
  var buttons = sorter.querySelectorAll("button");

  function sortBy(key) {
    var cards = Array.prototype.slice.call(list.children);
    cards.sort(function (a, b) {
      return parseFloat(b.dataset[key]) - parseFloat(a.dataset[key]);
    });
    cards.forEach(function (card) { list.appendChild(card); });
    buttons.forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.sort === key));
    });
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () { sortBy(button.dataset.sort); });
  });
})();
