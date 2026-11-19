// Point the download button at the newest Windows zip and fill in its version, date and size.
// Without this script (or when GitHub's API does not answer) the button leads to the releases page.
(function () {
  "use strict";
  var REPO = "BudongJW/stream2clip";
  var buttons = document.querySelectorAll("[data-download]");
  if (!buttons.length || !window.fetch) return;

  function fill(name, text) {
    document.querySelectorAll('[data-release="' + name + '"]').forEach(function (node) {
      node.textContent = text;
    });
  }

  fetch("https://api.github.com/repos/" + REPO + "/releases/latest", { headers: { Accept: "application/vnd.github+json" } })
    .then(function (response) {
      if (!response.ok) throw new Error("GitHub API " + response.status);
      return response.json();
    })
    .then(function (release) {
      var asset = (release.assets || []).filter(function (a) {
        return /windows-x64\.zip$/.test(a.name);
      })[0];
      if (!asset) return;
      buttons.forEach(function (button) {
        button.href = asset.browser_download_url;
        button.setAttribute("download", "");
      });
      fill("version", release.tag_name);
      fill("date", (release.published_at || "").slice(0, 10));
      fill("size", Math.round(asset.size / 1048576) + "MB");
    })
    .catch(function () {
      /* keep the link to the releases page */
    });
})();
