(function(){
  const btn=document.getElementById('voice-start');
  if(!btn)return;
  btn.addEventListener('click',function(){
    const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
    const status=document.getElementById('voice-status');
    if(!Recognition){status.textContent='Speech recognition unavailable in this browser. Use text search.';return;}
    const r=new Recognition();r.lang='en-US';r.interimResults=false;r.maxAlternatives=1;
    r.onresult=e=>{let q=e.results[0][0].transcript;status.textContent='Searching for: '+q;
      window.location.href='/?q='+encodeURIComponent(q);};
    r.onerror=()=>{status.textContent='Speech unavailable. Use the catalog search field.';};
    r.start();status.textContent='Listening...';
  });
})();
