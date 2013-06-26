(function() {
  var lastHash = null;
  var logName = 'system_logs';
  window.addEventListener('click', function() {
    // The hashchange event doesn't fire on the list of reports page, so we
    // check after every click.
    if (window.location.hash !== lastHash) {
      lastHash = window.location.hash;
      var spans = document.getElementsByTagName('span');
      for (var i = 0; i < spans.length; i++) {
        var span = spans[i];
        var logIndex = span.innerHTML.indexOf(logName);

        // Only add a button if system_log is one of the files available
        if (logIndex !== -1 && span.parentNode && span.parentNode.parentNode) {
          var button = document.createElement('button');
          button.setAttribute('type', 'button');
          button.innerHTML = 'View touch logs';
          button.addEventListener('click', function() {
            chrome.runtime.sendMessage({
              'reportUrl': span.parentNode.href,
            });
          });

          // Add the button that links to the log viewer beside the anchor
          // containing the span element.
          span.parentNode.parentNode.appendChild(button);
          break;
        }
      }
    }
  });
})();
