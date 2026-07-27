// Anchor-nav scrollspy + student upload helpers.
(function () {
  "use strict";
  function initScrollSpy() {
    var nav = document.querySelector(".anchor-nav");
    if (!nav || !("IntersectionObserver" in window)) return;
    var links = Array.prototype.slice.call(nav.querySelectorAll("a[href^='#']"));
    var byId = {};
    var sections = [];
    links.forEach(function (a) {
      var id = a.getAttribute("href").slice(1);
      var el = document.getElementById(id);
      if (el) { byId[id] = a; sections.push(el); }
    });
    if (!sections.length) return;

    function setActive(id) {
      links.forEach(function (a) { a.classList.remove("is-active"); });
      if (byId[id]) byId[id].classList.add("is-active");
    }
    setActive(sections[0].id);

    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) setActive(e.target.id);
      });
    }, { rootMargin: "-74px 0px -55% 0px", threshold: 0 });
    sections.forEach(function (s) { obs.observe(s); });
  }

  function initUploadCards() {
    var cards = Array.prototype.slice.call(document.querySelectorAll("[data-upload-card]"));
    cards.forEach(function (card) {
      var input = card.querySelector("[data-upload-input]");
      var line = card.querySelector("[data-file-line]");
      var name = card.querySelector("[data-file-name]");
      var clear = card.querySelector("[data-clear-file]");
      if (!input || !line || !name || !clear) return;
      input.addEventListener("change", function () {
        if (input.files && input.files.length) {
          name.textContent = input.files[0].name;
          line.hidden = false;
        } else {
          name.textContent = "";
          line.hidden = true;
        }
      });
      clear.addEventListener("click", function () {
        input.value = "";
        name.textContent = "";
        line.hidden = true;
        input.focus();
      });
    });
  }

  function init() {
    initScrollSpy();
    initUploadCards();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
