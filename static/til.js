// Progressive enhancement only: every page works with JavaScript disabled.
(function () {
  "use strict";

  addCopyButtons();
  wireSearch();

  function addCopyButtons() {
    if (!navigator.clipboard) return;
    document.querySelectorAll(".code-block").forEach(function (block) {
      var code = block.querySelector("code");
      if (!code) return;
      var button = document.createElement("button");
      button.type = "button";
      button.className = "copy-button";
      button.textContent = "Copy";
      button.addEventListener("click", function () {
        navigator.clipboard.writeText(code.textContent).then(
          function () { flash(button, "Copied"); },
          function () { flash(button, "Failed"); }
        );
      });
      block.appendChild(button);
    });
  }

  function flash(button, message) {
    button.textContent = message;
    setTimeout(function () { button.textContent = "Copy"; }, 1200);
  }

  function wireSearch() {
    var input = document.querySelector("[data-search-root] input");
    var list = document.querySelector("[data-til-list]");
    if (!input || !list) return;

    var status = document.querySelector("[data-search-status]");
    var empty = document.querySelector("[data-empty]");
    var items = Array.prototype.slice.call(list.children);
    var bodies = null; // url -> full text, loaded lazily from search.json

    items.forEach(function (item) {
      item.dataset.haystack = [
        item.dataset.title || "",
        item.dataset.topic || "",
        item.dataset.tags || "",
        item.textContent
      ].join(" ").toLowerCase();
    });

    input.addEventListener("input", function () {
      loadBodies();
      filter(input.value);
    });

    var initial = new URLSearchParams(location.search).get("q");
    if (initial) {
      input.value = initial;
      loadBodies();
      filter(initial);
    }

    function loadBodies() {
      if (bodies !== null) return;
      bodies = {}; // only attempt the fetch once
      // file:// pages cannot fetch; titles-and-summaries search still works.
      if (location.protocol === "file:") return;
      fetch("search.json")
        .then(function (response) { return response.json(); })
        .then(function (data) {
          (data.items || []).forEach(function (entry) {
            bodies[entry.url] = (entry.text || "").toLowerCase();
          });
          filter(input.value);
        })
        .catch(function () { /* file:// or offline: titles-only search still works */ });
    }

    function filter(query) {
      var tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
      var shown = 0;
      items.forEach(function (item) {
        var haystack = item.dataset.haystack + " " + (bodies[item.dataset.url] || "");
        var match = tokens.every(function (token) { return haystack.indexOf(token) !== -1; });
        item.hidden = !match;
        if (match) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
      if (status) {
        status.textContent = tokens.length
          ? shown + " of " + items.length + " case files match"
          : "";
      }
    }
  }
})();
