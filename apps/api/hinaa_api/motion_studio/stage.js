/* Frame-clocked compositor. All motion is a pure function of time; media seeking is awaited. */
const C = COMPOSITION, W = C.width, H = C.height;
const canvas = document.getElementById('motion'), main = canvas.getContext('2d');
const surfaces = [document.createElement('canvas'), document.createElement('canvas')];
surfaces.forEach(c => { c.width = W; c.height = H; });
const contexts = surfaces.map(c => c.getContext('2d'));
const starts = []; let total = 0;
C.scenes.forEach(s => { starts.push(total); total += s.duration; });
const clamp = v => Math.max(0, Math.min(1, v));
const lerp = (a, b, p) => a + (b - a) * p;
function ease(x, kind = 'cubic') {
  const p = clamp(x);
  if (kind === 'linear') return p;
  if (kind === 'expo') return p >= 1 ? 1 : 1 - 2 ** (-10 * p);
  if (kind === 'spring') return p >= 1 ? 1 : 1 - Math.exp(-7 * p) * Math.cos(10 * p);
  return p * p * (3 - 2 * p);
}
const hash = n => { const f = Math.sin(n * 127.1 + 37.7) * 43758.5453; return f - Math.floor(f); };
const shaped = text => /[\p{Script=Devanagari}\p{Script=Arabic}\p{Script=Bengali}\p{Script=Thai}]/u.test(text);
function clusters(text) {
  if (!Intl.Segmenter) return [text];
  return Array.from(new Intl.Segmenter(undefined, {granularity:'grapheme'}).segment(text), s => s.segment);
}
function units(text, words) {
  return (words || shaped(text)) ? text.match(/\S+\s*/gu) || [text] : clusters(text);
}
function face(layer) {
  return layer.font === 'serif' ? 'Georgia, "Noto Serif Devanagari", serif' :
    layer.font === 'mono' ? '"DejaVu Sans Mono", monospace' :
    '"Arial Narrow", "DejaVu Sans", "Noto Sans Devanagari", sans-serif';
}
function accentAt(time) {
  let pulse = 0;
  for (const t of C.accents) if (time >= t && time-t < .32) pulse = Math.max(pulse, Math.exp(-(time-t)*18));
  return pulse;
}
function keyPose(layer, t) {
  const ks = layer.keyframes;
  if (!ks.length) return {x:0,y:0,scale:1,rotation:0,opacity:1};
  if (t <= ks[0].time) return ks[0];
  if (t >= ks[ks.length-1].time) return ks[ks.length-1];
  let b = 1; while (ks[b].time < t) b++;
  const a = ks[b-1], z = ks[b], p = ease((t-a.time)/(z.time-a.time), z.ease);
  const out = {};
  ['x','y','scale','rotation','opacity'].forEach(k => out[k] = lerp(a[k], z[k], p));
  return out;
}

const media = new Map();
const mediaKey = layer => layer.kind === 'video' ? layer : layer.src;
window.__motionReady = (async () => {
  const promises = [];
  for (const scene of C.scenes) for (const layer of scene.layers) {
    if (!layer.src || media.has(mediaKey(layer))) continue;
    const isVideo = layer.kind === 'video';
    const item = isVideo ? document.createElement('video') : new Image();
    if (isVideo) { item.muted = true; item.preload = 'auto'; item.playsInline = true; }
    media.set(mediaKey(layer), item);
    promises.push(new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Motion asset loading timed out')), 20000);
      item.addEventListener(isVideo ? 'loadeddata' : 'load', () => { clearTimeout(timer); resolve(); }, {once:true});
      item.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Motion asset cannot be decoded')); }, {once:true});
      item.src = layer.src;
    }));
  }
  await Promise.all(promises);
  await document.fonts.ready;
})();

async function seekMedia(indices, time) {
  const desired = new Map();
  for (const index of indices) {
    const scene = C.scenes[index], local = Math.max(0, Math.min(scene.duration-.00001, time-starts[index]));
    for (const l of scene.layers) {
      if (l.kind !== 'video' || local < l.start || local >= (l.end ?? scene.duration)) continue;
      const item = media.get(mediaKey(l));
      const target = Math.max(0, Math.min(item.duration-0.002, l.media_start + (local-l.start)*l.playback_rate));
      // One decoded element per source/time: conflicting reuse would otherwise race.
      if (desired.has(item) && Math.abs(desired.get(item)-target) > 0.002) throw new Error('Use distinct video sources for overlapping layers with different trims');
      desired.set(item, target);
    }
  }
  await Promise.all(Array.from(desired, ([item, target]) => new Promise((resolve, reject) => {
    if (Math.abs(item.currentTime-target) < 0.0005 && item.readyState >= 2) { resolve(); return; }
    const timer = setTimeout(() => { item.removeEventListener('seeked', done); reject(new Error('Video frame seek timed out')); }, 10000);
    function done() { clearTimeout(timer); resolve(); }
    item.addEventListener('seeked', done, {once:true}); item.currentTime = target;
  })));
}

function textLayout(ctx, layer) {
  let px = W * layer.size;
  const lines = layer.text.split('\n');
  const max = Math.min(W*layer.max_width, layer.align === 'left' ? W*(1-C.safe_margin-layer.x) :
    layer.align === 'right' ? W*(layer.x-C.safe_margin) : W*2*Math.min(layer.x-C.safe_margin, 1-C.safe_margin-layer.x));
  if (max <= 0) throw new Error('Text anchor falls outside safe margins');
  ctx.font = `${layer.weight} ${px}px ${face(layer)}`;
  const widths = lines.map(s => ctx.measureText(s).width + (shaped(s) ? 0 : Math.max(0,clusters(s).length-1)*px*layer.tracking));
  const scale = Math.min(1, max/Math.max(1,...widths)); px *= scale;
  ctx.font = `${layer.weight} ${px}px ${face(layer)}`;
  const lineHeight = px*1.15;
  const safeTop = H*C.safe_margin, safeBottom = H*(1-C.safe_margin);
  let y0 = H*layer.y-(lines.length-1)*lineHeight/2;
  y0 = Math.max(safeTop+px*.5, Math.min(safeBottom-px*.5-(lines.length-1)*lineHeight,y0));
  return {px, lines, lineHeight, y0};
}
function glyph(ctx, text, x, y, layer) {
  if (layer.outline) { ctx.strokeStyle = layer.stroke; ctx.lineWidth = Math.max(1.4,W*.0019); ctx.strokeText(text,x,y); }
  else ctx.fillText(text,x,y);
}
function textLayer(ctx, l, time, duration) {
  const {px,lines,lineHeight,y0} = textLayout(ctx,l);
  ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillStyle = l.color;
  let sequence = 0;
  lines.forEach((line, li) => {
    const separate = ['word_reveal','letter_stagger','typewriter'].includes(l.motion) || ((l.tracking !== 0 || l.motion === 'tracking') && !shaped(line));
    const chunks = separate ? units(line,l.motion === 'word_reveal') : [line];
    const spacing = shaped(line) ? 0 : px*l.tracking;
    const widths = chunks.map(s => ctx.measureText(s).width);
    const lineWidth = widths.reduce((a,b)=>a+b,0)+spacing*(chunks.length-1);
    let x = W*l.x - (l.align === 'center' ? lineWidth/2 : l.align === 'right' ? lineWidth : 0);
    for (let i=0;i<chunks.length;i++,sequence++) {
      const delay = l.unit_times.length ? (l.unit_times[sequence] ?? duration) : sequence*l.stagger;
      const raw = separate ? (time-delay)/l.entrance : time/l.entrance;
      const p = ease(raw,'expo');
      if (raw<0) { x+=widths[i]+spacing; continue; }
      const y = y0+li*lineHeight;
      ctx.save();
      if (l.motion === 'mask_rise' || l.motion === 'word_reveal') {
        ctx.beginPath();ctx.rect(x-5,y-px*.65,widths[i]+10,px*1.3);ctx.clip();
        ctx.translate(0,(1-p)*px*1.25);
      } else if (l.motion === 'letter_stagger') {
        ctx.globalAlpha *= clamp(raw*2); ctx.translate(0,(1-p)*px*.8);
        ctx.translate(x+widths[i]/2,y);ctx.rotate((1-p)*-.22);ctx.translate(-x-widths[i]/2,-y);
      } else if (l.motion === 'tracking') {
        ctx.translate((i-(chunks.length-1)/2)*(1-p)*px*.7,0);ctx.globalAlpha *= p;
      } else if (l.motion === 'perspective') {
        ctx.translate(x,y);ctx.transform(1,0,(1-p)*.65,Math.max(.03,p),0,0);ctx.translate(-x,-y);
      } else if (l.motion === 'blur_rise') {
        ctx.filter = `blur(${(1-p)*px*.1}px)`;ctx.globalAlpha*=p;ctx.translate(0,(1-p)*px*.5);
      } else if (l.motion === 'typewriter' && raw < .1) { ctx.restore();x+=widths[i]+spacing;continue;
      } else if (l.motion === 'scale_pop') {
        const pop = ease(raw,'spring');ctx.translate(x+widths[i]/2,y);ctx.scale(Math.max(.01,pop),Math.max(.01,pop));ctx.translate(-x-widths[i]/2,-y);
      }
      if (l.motion === 'slash') {
        const split = Math.max(0,Math.sin(clamp((time-.65)/.55)*Math.PI))*px*.12;
        ctx.save();ctx.beginPath();ctx.rect(x-5,y-px,widths[i]+10,px);ctx.clip();glyph(ctx,chunks[i],x-split,y,l);ctx.restore();
        ctx.save();ctx.beginPath();ctx.rect(x-5,y,widths[i]+10,px);ctx.clip();glyph(ctx,chunks[i],x+split,y,l);ctx.restore();
      } else glyph(ctx,chunks[i],x,y,l);
      ctx.restore();x+=widths[i]+spacing;
    }
  });
}

function paintLayer(ctx, l, local, duration, global, ghost = false) {
  if (local<l.start || local>=(l.end ?? duration)) return;
  const t = local-l.start, span=(l.end ?? duration)-l.start, k=keyPose(l,t);
  const ending = clamp((span-t)/Math.min(.18,span*.1));
  ctx.save(); ctx.globalCompositeOperation=l.blend;ctx.globalAlpha=l.opacity*k.opacity*ending*(ghost ? .14 : 1);
  const pulse = accentAt(global);
  ctx.translate(k.x*W + Math.sin(global*.7)*l.depth*W*.012,k.y*H + Math.cos(global*.65)*l.depth*H*.006);
  ctx.translate(l.x*W,l.y*H);ctx.rotate(k.rotation*Math.PI/180);ctx.scale(k.scale,k.scale);ctx.translate(-l.x*W,-l.y*H);
  if (l.kind === 'text') textLayer(ctx,l,t,span);
  else if (l.kind === 'image' || l.kind === 'video') {
    const item=media.get(mediaKey(l)), iw=item.videoWidth || item.naturalWidth, ih=item.videoHeight || item.naturalHeight;
    const bw=W*l.size,bh=H*l.height;
    const scale=(l.fit === 'cover' ? Math.max : Math.min)(bw/iw,bh/ih);
    ctx.beginPath();ctx.rect(l.x*W-bw/2,l.y*H-bh/2,bw,bh);ctx.clip();
    ctx.drawImage(item,l.x*W-iw*scale/2,l.y*H-ih*scale/2,iw*scale,ih*scale);
  } else {
    const p=ease(t/l.entrance,'expo'),x=l.x*W,y=l.y*H;
    ctx.strokeStyle=l.stroke;ctx.fillStyle=l.color;ctx.lineWidth=Math.max(1.5,W*.002);
    if(l.kind==='rect')ctx.fillRect(x-W*l.size/2,y-H*l.height/2,W*l.size*p,H*l.height);
    if(l.kind==='line'){ctx.beginPath();ctx.moveTo(x-W*l.size/2,y);ctx.lineTo(x-W*l.size/2+W*l.size*p,y);ctx.stroke();}
    if(l.kind==='ring'){ctx.beginPath();ctx.ellipse(x,y,W*l.size*(1+pulse*.04)/2,H*l.height/2,0,-Math.PI/2,-Math.PI/2+Math.PI*2*p);ctx.stroke();}
  }
  ctx.restore();
}
function drawScene(index, global, ctx) {
  const s=C.scenes[index], local=Math.max(0,Math.min(s.duration-.00001,global-starts[index])), p=local/s.duration;
  ctx.clearRect(0,0,W,H);ctx.fillStyle=s.background;ctx.fillRect(0,0,W,H);ctx.save();
  const a=s.camera_amount, e=ease(p), hit=accentAt(global);
  let z=1,dx=0,dy=0,r=0;
  if(s.camera==='dolly') z=1+a*e;
  if(s.camera==='pan_left' || s.camera==='pan_right'){z=1+a;dx=(s.camera==='pan_left'?-1:1)*(p-.5)*a*W;}
  if(s.camera==='orbit'){z=1+a*.8;dx=Math.sin(p*Math.PI)*a*W*.3;dy=Math.cos(p*Math.PI)*a*H*.08;r=Math.sin(p*Math.PI*2)*a*.15;}
  if(s.camera==='crash_zoom')z=1+a*e+a*hit*.25;
  ctx.translate(W/2+dx,H/2+dy);ctx.scale(z,z);ctx.rotate(r);ctx.translate(-W/2,-H/2);
  for(const l of s.layers){
    if(l.motion_blur && l.kind!=='video')for(const lag of [.014,.028])paintLayer(ctx,l,local-lag,s.duration,global-lag,true);
    paintLayer(ctx,l,local,s.duration,global);
  }
  ctx.restore();
  if(s.atmosphere!=='none'){
    ctx.save();ctx.fillStyle=s.accent;
    for(let i=0;i<32;i++){
      const x=(hash(i)*W+Math.sin(global*.45+i)*W*.018)%W;
      const y=((hash(i+31)*H-global*(12+i%9*5))%H+H)%H;
      ctx.globalAlpha=(.1+hash(i+90)*.35)*(s.atmosphere==='dust'?.45:1);
      ctx.beginPath();ctx.arc(x,y,1+hash(i+13)*W*.002,0,Math.PI*2);ctx.fill();
    }ctx.restore();
  }
}
window.setAnimationTime = async function(time) {
  await window.__motionReady;
  const t=Math.max(0,Math.min(total-.00001,time));let i=0;
  while(i<C.scenes.length-1 && t>=starts[i+1])i++;
  const s=C.scenes[i],local=t-starts[i],td=Math.min(s.transition_duration,s.duration*.5);
  const trans=i>0 && local<td && s.transition!=='cut';
  await seekMedia(trans?[i-1,i]:[i],t);
  drawScene(i,t,contexts[0]);main.clearRect(0,0,W,H);
  if(!trans){main.drawImage(surfaces[0],0,0);return;}
  drawScene(i-1,starts[i]-.001,contexts[1]);main.drawImage(surfaces[1],0,0);
  const p=ease(local/td,'cubic');main.save();
  if(s.transition==='crossfade')main.globalAlpha=p;
  if(s.transition==='wipe'){main.beginPath();main.rect(0,0,W*p,H);main.clip();}
  if(s.transition==='diagonal'){
    const edge=-W*.35+p*W*1.7;main.beginPath();main.moveTo(0,0);main.lineTo(edge+W*.3,0);main.lineTo(edge-W*.3,H);main.lineTo(0,H);main.closePath();main.clip();
  }
  if(s.transition==='iris'){main.beginPath();main.arc(W/2,H/2,Math.hypot(W,H)*.51*p,0,Math.PI*2);main.clip();}
  if(s.transition==='whip'){
    main.drawImage(surfaces[1],-W*p,0);main.translate(W*(1-p),0);main.filter=`blur(${Math.sin(p*Math.PI)*W*.009}px)`;
  }
  main.drawImage(surfaces[0],0,0);main.restore();
};
let playing=false;
window.playMotion = async function(){
  if(playing){playing=false;return;}playing=true;let start;
  async function tick(now){if(!playing)return;start??=now;await window.setAnimationTime(((now-start)/1000)%total);requestAnimationFrame(tick);}
  requestAnimationFrame(tick);
};
document.addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();window.playMotion();}});
