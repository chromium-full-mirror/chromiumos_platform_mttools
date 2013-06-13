(function() {
  chrome.browserAction.onClicked.addListener(function() {
    console.log('Opening new touch viewer...');
    chrome.tabs.create({
      'url': chrome.extension.getURL('mtedit.html'),
    });
  });

  if (chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener(
        function(request, sender, sendResponse) {
          if (request.reportId !== undefined &&
              request.extension !== undefined) {
            chrome.tabs.create({
              'url': chrome.extension.getURL('mtedit.html') +
                  '#reportId=' + request.reportId +
                  '&extension=' + request.extension,
            });
          }
        });
  } else {
    console.log('Please update chrome, seriously. ;)');
  }
})();
