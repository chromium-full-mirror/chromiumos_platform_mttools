(function() {
  if (chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener(
        function(request, sender, sendResponse) {
          if (request.reportUrl !== undefined) {
            chrome.tabs.create({
              'url': chrome.extension.getURL('mtedit.html') +
                  '#reportUrl=' + encodeURIComponent(request.reportUrl),
            });
          }
        });
  } else {
    console.log('Please update chrome, seriously. ;)');
  }
})();
