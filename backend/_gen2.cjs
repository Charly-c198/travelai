const B='http://127.0.0.1:8000';
(async()=>{
  const tok=(await fetch(B+'/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).catch(()=>null));
})();
