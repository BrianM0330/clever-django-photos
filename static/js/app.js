// Shared frontend glue. Loaded as a normal script after Alpine + HTMX.
// Keep this tiny — most behavior lives next to the markup via Alpine x-data
// or HTMX attributes on the relevant element.

(function () {
  // Surface a single global so templates can do {% if debug %}console.log(window.app)…{% endif %}
  window.app = window.app || {};

  // Wire HTMX <-> Django messages: when a server response includes the
  // `HX-Trigger: showMessage` header with a JSON payload, dispatch a CustomEvent
  // that any Alpine toast component can listen for.
  document.body.addEventListener("showMessage", (evt) => {
    const detail = evt.detail || {};
    // Default to console; real toast component lands with the gallery UI.
    console.info("[flash]", detail.level || "info", detail.message || detail);
  });
})();
