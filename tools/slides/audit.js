// node audit.js   — в папке с print.html: контраст текста, мелкий шрифт (<20 px), выход за край, наезд на колонтитул.
// Печатает «no issues» или список замечаний (CONTRAST / SMALL / OUT / LOW / CLIP).
const { chromium } = require('playwright');
function parse(c){const m=c.match(/rgba?\(([^)]+)\)/); if(!m) return null; const p=m[1].split(',').map(Number); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1};}
function lum(c){const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b);}
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium' });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + process.cwd() + '/print.html', { waitUntil: 'networkidle', timeout: 60000 }).catch(()=>{});
  await p.evaluate(() => document.fonts.ready);
  const res = await p.evaluate(() => {
    const out=[]; const secs=[...document.querySelectorAll('section')];
    function bg(el){ while(el){ const c=getComputedStyle(el).backgroundColor; const m=c.match(/rgba?\(([^)]+)\)/); if(m){const v=m[1].split(',').map(Number); if(v.length<4||v[3]>0.5) return c;} el=el.parentElement;} return 'rgb(255,255,255)'; }
    secs.forEach((s,i)=>{
      const sr=s.getBoundingClientRect();
      s.querySelectorAll('p,h1,h2,h3,li,span,b').forEach(el=>{
        if(!el.childNodes.length) return;
        const hasText=[...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim());
        if(!hasText) return;
        const cs=getComputedStyle(el); const r=el.getBoundingClientRect();
        out.push({slide:i+1,text:el.textContent.trim().slice(0,40),fs:parseFloat(cs.fontSize),color:cs.color,bg:bg(el),
          top:r.top-sr.top,bottom:r.bottom-sr.top,left:r.left-sr.left,right:r.right-sr.left,abs:cs.position==='absolute',clip:el.scrollWidth>el.clientWidth+1});
      });
    });
    return out;
  });
  const issues=[];
  for(const e of res){
    const c=parse(e.color), g=parse(e.bg); if(!c||!g) continue;
    const l1=lum(c), l2=lum(g); const ratio=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
    const need = e.fs>=24 ? 3 : 4.5;
    if(ratio<need) issues.push(['CONTRAST',e.slide,e.text,e.fs,ratio.toFixed(2)]);
    if(e.fs<20) issues.push(['SMALL',e.slide,e.text,e.fs]);
    if(e.bottom>1075||e.right>1915||e.left<0) issues.push(['OUT',e.slide,e.text,Math.round(e.bottom),Math.round(e.right)]);
    if(!e.abs && e.bottom>975) issues.push(['LOW',e.slide,e.text,Math.round(e.bottom)]);
    if(e.clip) issues.push(['CLIP',e.slide,e.text]);
  }
  console.log(issues.map(i=>i.join(' | ')).join('\n')||'no issues');
  await b.close();
})();
