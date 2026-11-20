// Ayudas de navegación de todas las páginas. Sin JavaScript la página se ve entera y bien;
// esto solo la hace más cómoda:
// - Índice "En esta página" con las secciones (las que tienen id y título).
// - Al llegar a una sección por enlace (#id), si estaba plegada se abre.
// - En el móvil, las tablas con muchas columnas enseñan solo las primeras y un botón para
//   ver todas.
// - Botón "Imprimir" (página de la previa).
(function () {
  "use strict";
  var main = document.querySelector("main");
  if (!main) return;

  // Índice de la página.
  var sections = Array.prototype.filter.call(
    main.querySelectorAll("section[id]"),
    function (s) { return s.querySelector("h2") && s.id !== "glosario"; }
  );
  if (sections.length >= 3) {
    var nav = document.createElement("nav");
    nav.className = "toc";
    nav.setAttribute("aria-label", "En esta página");
    var label = document.createElement("span");
    label.textContent = "En esta página";
    nav.appendChild(label);
    sections.forEach(function (s) {
      var a = document.createElement("a");
      a.href = "#" + s.id;
      a.textContent = s.querySelector("h2").textContent.trim();
      nav.appendChild(a);
    });
    // Después de la cabecera de la página (la primera tarjeta o bloque).
    var first = main.firstElementChild;
    while (first && (first.matches("p.back") || first.matches("script"))) {
      first = first.nextElementSibling;
    }
    main.insertBefore(nav, first ? first.nextElementSibling : main.firstChild);
  }

  // Abre la sección plegada a la que apunta el enlace.
  function openTarget() {
    var id = decodeURIComponent(location.hash.slice(1));
    if (!id) return;
    var target = document.getElementById(id);
    if (!target) return;
    var details = target.matches("details") ? target : target.querySelector("details");
    for (var el = target; el; el = el.parentElement) {
      if (el.tagName === "DETAILS") el.open = true;
    }
    if (details && !details.open) details.open = true;
    target.scrollIntoView();
  }
  window.addEventListener("hashchange", openTarget);
  openTarget();

  // Un gráfico dibujado dentro de una sección plegada no sabe su ancho: al abrirla, se ajusta.
  document.addEventListener("toggle", function (event) {
    var details = event.target;
    if (!details.open || !window.Plotly) return;
    Array.prototype.forEach.call(details.querySelectorAll(".plotly-graph-div"), function (g) {
      window.Plotly.Plots.resize(g);
    });
  }, true);

  // Tablas anchas en el móvil: primeras columnas y botón para ver todas.
  var VISIBLE = 4; // columnas además de la primera (nombre)
  if (window.matchMedia("(max-width: 699px)").matches) {
    Array.prototype.forEach.call(document.querySelectorAll("table.data"), function (table) {
      var header = table.querySelector("thead tr:last-child");
      if (!header || header.children.length <= VISIBLE + 2 || table.matches(".compare")) return;
      table.classList.add("compact");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "more-columns";
      var hidden = header.children.length - VISIBLE - 1;
      button.textContent = "Ver las " + hidden + " columnas que faltan";
      button.addEventListener("click", function () {
        var compact = table.classList.toggle("compact");
        button.textContent = compact
          ? "Ver las " + hidden + " columnas que faltan"
          : "Ver menos columnas";
      });
      var wrap = table.closest(".table-wrap") || table;
      wrap.parentNode.insertBefore(button, wrap.nextSibling);
    });
  }

  // Imprimir: abre todo lo plegado antes de imprimir.
  Array.prototype.forEach.call(document.querySelectorAll("[data-print]"), function (button) {
    button.hidden = false;
    button.addEventListener("click", function () { window.print(); });
  });
  window.addEventListener("beforeprint", function () {
    Array.prototype.forEach.call(document.querySelectorAll("main details"), function (d) {
      if (!d.closest(".glossary") && !d.closest(".how")) d.open = true;
    });
  });
})();
