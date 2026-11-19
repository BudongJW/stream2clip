// Point the download buttons at the newest Windows zip and show its version and size.
// Without this script (or when GitHub's API does not answer) the buttons lead to the releases page.
(function () {
  "use strict";
  var REPO = "BudongJW/stream2clip";
  var buttons = document.querySelectorAll("[data-download]");
  var notes = document.querySelectorAll("[data-release]");
  if (!buttons.length || !window.fetch) return;

  function megabytes(bytes) {
    return Math.round(bytes / 1048576) + "MB";
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
      var day = (release.published_at || "").slice(0, 10);
      var text = [release.tag_name, day, megabytes(asset.size), "zip"].filter(Boolean).join(" · ");
      notes.forEach(function (note) {
        note.textContent = text;
      });
    })
    .catch(function () {
      /* keep the links to the releases page */
    });
})();
