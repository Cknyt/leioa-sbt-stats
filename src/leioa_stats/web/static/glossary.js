// Añade un botón "?" junto a cada término técnico (cabeceras de tabla y etiquetas con
// data-term). Al tocarlo (móvil) o pasar el ratón (ordenador) muestra su definición.
(function () {
  "use strict";
  var source = document.getElementById("glossary-data");
  if (!source) return;
  var terms = JSON.parse(source.textContent);

  // Variantes que se explican a partir del término base.
  var SUFFIXES = [
    ["/PJ", " Media por partido jugado."],
    ["/40", " Por cada 40 minutos en pista."],
  ];

  function define(label) {
    label = label.trim();
    if (terms[label]) return terms[label];
    for (var i = 0; i < SUFFIXES.length; i++) {
      var suffix = SUFFIXES[i][0];
      if (label.slice(-suffix.length) === suffix) {
        var base = terms[label.slice(0, -suffix.length)];
        if (base) return base + SUFFIXES[i][1];
      }
    }
    if (label.slice(-6) === " rival") {
      var own = terms[label.slice(0, -6)];
      if (own) return "Lo mismo, pero de los rivales: lo que permite su defensa. " + own;
    }
    return null;
  }

  var tip = document.createElement("div");
  tip.className = "tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);
  var current = null;
  // Fijada con un toque o clic: no se cierra al apartar el ratón.
  var pinned = false;

  function show(button) {
    tip.innerHTML = "";
    var title = document.createElement("strong");
    title.textContent = button.dataset.term;
    tip.appendChild(title);
    tip.appendChild(document.createTextNode(" " + button.dataset.tip));
    tip.hidden = false;
    var r = button.getBoundingClientRect();
    var width = tip.offsetWidth;
    var left = Math.min(Math.max(8, r.left + r.width / 2 - width / 2), window.innerWidth - width - 8);
    var top = r.bottom + 6;
    if (top + tip.offsetHeight > window.innerHeight - 8) top = r.top - tip.offsetHeight - 6;
    tip.style.left = left + "px";
    tip.style.top = Math.max(8, top) + "px";
    current = button;
  }

  function hide() {
    tip.hidden = true;
    current = null;
    pinned = false;
  }

  var labels = document.querySelectorAll("thead th, tbody th, [data-term]");
  Array.prototype.forEach.call(labels, function (el) {
    var label = el.dataset.term || el.textContent;
    if (!label || el.querySelector("a")) return;
    var text = define(label);
    if (!text) return;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "info";
    button.textContent = "?";
    button.dataset.term = label.trim();
    button.dataset.tip = text;
    button.setAttribute("aria-label", "Qué es " + label.trim());
    el.appendChild(button);
  });

  document.addEventListener("click", function (event) {
    var button = event.target.closest("button.info");
    if (!button) return hide();
    event.preventDefault();
    if (current === button && pinned) return hide();
    show(button);
    pinned = true;
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") hide();
  });
  // Con ratón, también al pasar por encima.
  if (window.matchMedia("(hover: hover)").matches) {
    document.addEventListener("mouseover", function (event) {
      var button = event.target.closest && event.target.closest("button.info");
      if (button && !pinned && button !== current) show(button);
    });
    document.addEventListener("mouseout", function (event) {
      var button = event.target.closest && event.target.closest("button.info");
      if (button && !pinned) hide();
    });
  }
  window.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);
})();
