// Language menu, and the download button: it is pointed at the newest Windows zip, with its version and size filled in.
// Without this script (or when GitHub's API does not answer) the button leads to the releases page.
(function () {
  "use strict";
  // The language menu closes on a click elsewhere and on Escape.
  var menu = document.querySelector("details.lang");
  if (menu) {
    document.addEventListener("click", function (event) {
      if (!menu.contains(event.target)) menu.removeAttribute("open");
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") menu.removeAttribute("open");
    });
  }

  var REPO = "BudongJW/stream2clip";
  var buttons = document.querySelectorAll("[data-download]");
  if (!buttons.length || !window.fetch) return;

  function fill(name, text) {
    document.querySelectorAll('[data-release="' + name + '"]').forEach(function (node) {
      node.textContent = text;
    });
  }

  function find(assets, pattern) {
    return assets.filter(function (asset) {
      return pattern.test(asset.name);
    })[0];
  }

  fetch("https://api.github.com/repos/" + REPO + "/releases/latest", { headers: { Accept: "application/vnd.github+json" } })
    .then(function (response) {
      if (!response.ok) throw new Error("GitHub API " + response.status);
      return response.json();
    })
    .then(function (release) {
      var assets = release.assets || [];
      var zip = find(assets, /windows-x64\.zip$/);
      var setup = find(assets, /windows-x64-setup\.exe$/) || zip; // a release from before the installer existed
      buttons.forEach(function (button) {
        var asset = button.getAttribute("data-download") === "zip" ? zip : setup;
        if (!asset) return;
        button.href = asset.browser_download_url;
        button.setAttribute("download", "");
      });
      if (!setup) return;
      fill("version", release.tag_name);
      fill("size", Math.round(setup.size / 1048576) + "MB");
    })
    .catch(function () {
      /* keep the links to the releases page */
    });
})();
