// Diario de visitas: avisa a registrar.php de qué página se abre, cuánto tiempo está visible
// y qué secciones llegan a verse. No guarda nada en el aparato (ni cookies ni almacenamiento
// del navegador) y no envía datos personales: el servidor apunta la hora y el aparato.
(function () {
  "use strict";
  var script = document.currentScript;
  // Al revisar la web en local no hay PHP: no se envía nada.
  if (!script || !window.navigator.sendBeacon || location.protocol === "file:") return;
  var host = location.hostname;
  if (host === "localhost" || host === "127.0.0.1") return;

  var endpoint = script.getAttribute("data-endpoint");
  var PING_SECONDS = 30;
  // Código de esta página abierta, para juntar sus avisos. Desaparece al cerrarla.
  var view = Math.random().toString(36).slice(2, 12) + Date.now().toString(36);

  function send(data) {
    data.v = view;
    navigator.sendBeacon(endpoint, JSON.stringify(data));
  }

  // Tiempo visible: solo cuenta mientras la pestaña está delante.
  var visibleMs = 0;
  var visibleSince = document.visibilityState === "visible" ? Date.now() : null;
  var lastSent = -1;

  function seconds() {
    var ms = visibleMs + (visibleSince ? Date.now() - visibleSince : 0);
    return Math.round(ms / 1000);
  }

  function ping() {
    var s = seconds();
    if (s !== lastSent) {
      lastSent = s;
      send({ t: "ping", s: s });
    }
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
      visibleSince = Date.now();
    } else if (visibleSince) {
      visibleMs += Date.now() - visibleSince;
      visibleSince = null;
      ping(); // Al salir de la pestaña o cerrar la página, último aviso.
    }
  });
  setInterval(function () {
    if (visibleSince) ping();
  }, PING_SECONDS * 1000);

  send({
    t: "start",
    p: location.pathname + location.hash,
    r: document.referrer ? new URL(document.referrer).hostname : "",
    // Pantalla y densidad de píxeles: ayudan a distinguir aparatos con el mismo navegador.
    w: screen.width + "x" + screen.height + "@" + Math.round((window.devicePixelRatio || 1) * 100) / 100,
  });

  // Secciones de la página (las que tienen id) que pasan por el centro de la pantalla. Se usa
  // una franja central y no un porcentaje de la sección porque algunas son más altas que la
  // pantalla y nunca se verían enteras.
  if (window.IntersectionObserver) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            send({ t: "section", id: entry.target.id });
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "-40% 0px -40% 0px" }
    );
    document.querySelectorAll("main section[id]").forEach(function (section) {
      observer.observe(section);
    });
  }
})();
