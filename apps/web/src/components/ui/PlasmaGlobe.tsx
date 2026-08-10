import { useEffect, useRef } from "react";

interface PlasmaGlobeProps {
  speed?: number;
  intensity?: number;
  className?: string;
}

const VERTEX_SHADER = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}`;

const FRAGMENT_SHADER = `#version 300 es
precision highp float;
out vec4 fragColor;
uniform float uTime;
uniform vec2 uResolution;
uniform vec2 uMouse;
uniform float uSpeed;
uniform float uIntensity;
#define NUM_RAYS 13.0
#define VOLUMETRIC_STEPS 19
#define MAX_ITER 35
#define FAR 6.0
mat2 mm2(float a){float c=cos(a),s=sin(a);return mat2(c,-s,s,c);}
float hash1(float n){return fract(sin(n)*43758.5453);}
float hash2(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise3(vec3 p){
  vec3 ip=floor(p),fp=fract(p);fp=fp*fp*(3.0-2.0*fp);
  float n000=hash2(ip.xy+ip.z*7.0),n100=hash2(ip.xy+vec2(1,0)+ip.z*7.0);
  float n010=hash2(ip.xy+vec2(0,1)+ip.z*7.0),n110=hash2(ip.xy+vec2(1,1)+ip.z*7.0);
  float nxy=mix(mix(n000,n100,fp.x),mix(n010,n110,fp.x),fp.y);
  return mix(nxy,hash1(ip.z+1.0),fp.z);
}
float flow(vec3 p,float t){
  float rz=0.0;vec3 bp=p;float z=2.0;
  for(int i=1;i<5;i++){p+=t*0.1;rz+=(sin(noise3(p+t*0.8)*6.0)*0.5+0.5)/z;p=mix(bp,p,0.6);z*=2.0;p*=2.01;}
  return rz;
}
float sins(float x,float t){float rz=0.0,z=2.0;for(int i=0;i<3;i++){rz+=abs(fract(x*1.4)-0.5)/z;x*=1.3;z*=1.15;x-=t*0.65*z;}return rz;}
float segm(vec3 p,vec3 a,vec3 b){vec3 pa=p-a,ba=b-a;float h=clamp(dot(pa,ba)/dot(ba,ba),0.0,1.0);return length(pa-ba*h)*0.5;}
vec3 path(float i,float d,float t){
  float sns2=sins(d+i*0.5,t)*0.22,sns=sins(d+i*0.6,t)*0.21;
  float a1=(hash1(i*10.569)-0.5)*6.2+sns2,a2=(hash1(i*4.732)-0.5)*6.2+sns;
  vec3 en=vec3(0,0,1);en.xz*=mat2(cos(a1),-sin(a1),sin(a1),cos(a1));en.xy*=mat2(cos(a2),-sin(a2),sin(a2),cos(a2));
  return en;
}
vec2 map2(vec3 p,float i,float t){
  float lp=length(p);vec3 bg=vec3(0),en=path(i,lp,t);
  float ins=smoothstep(0.11,0.46,lp),outs=0.15+smoothstep(0.0,0.15,abs(lp-1.0));
  p*=ins*outs;float id=ins*outs;float rz=segm(p,bg,en)-0.011;return vec2(rz,id);
}
vec2 iSphere2(vec3 ro,vec3 rd){vec3 oc=ro;float b=dot(oc,rd),c=dot(oc,oc)-1.0,h=b*b-c;if(h<0.0)return vec2(-1);return vec2(-b-sqrt(h),-b+sqrt(h));}
vec3 vmarch(vec3 ro,vec3 rd,float j,vec3 orig,float t){
  vec3 p=ro,sum=vec3(0);
  for(int i=0;i<VOLUMETRIC_STEPS;i++){
    vec2 r=map2(p,j,t);p+=rd*0.03;float lp=length(p);
    vec3 col=sin(vec3(1.05,2.5,1.52)*3.94+r.y)*0.85+0.4;
    col*=smoothstep(0.0,0.015,-r.x);col*=smoothstep(0.04,0.2,abs(lp-1.1));col*=smoothstep(0.1,0.34,lp);
    float n=noise3(vec3(lp*2.0+j*13.0+t*5.0));
    float denom=max(0.0001,log(max(0.0001,distance(p,orig)-2.0))+0.75);
    sum+=abs(col)*5.0*(1.2-n*1.1)/denom;
  }
  return sum;
}
float march2(vec3 ro,vec3 rd,float s,float mx,float j,float t){
  float h=0.5,d=s;
  for(int i=0;i<MAX_ITER;i++){if(abs(h)<0.001||d>mx)break;d+=h*1.2;float r=map2(ro+rd*d,j,t).x;h=r;}
  return d;
}
void main(){
  vec2 uv=(gl_FragCoord.xy/uResolution.xy)-0.5;uv.x*=uResolution.x/uResolution.y;
  vec2 um=(uMouse.xy/uResolution.xy)-0.5;
  vec3 ro=vec3(0,0,5),rd=normalize(vec3(uv*0.7,-1.5));
  mat2 mx=mm2(uTime*0.4+um.x*6.0),my=mm2(uTime*0.3+um.y*6.0);
  ro.xz*=mx;rd.xz*=mx;ro.xy*=my;rd.xy*=my;
  vec3 bro=ro,brd=rd,col=vec3(0);
  for(float j=1.0;j<NUM_RAYS+1.0;j++){
    ro=bro;rd=brd;
    mat2 mm=mm2((uTime*0.1+((j+1.0)*5.1))*j*0.25);
    ro.xy*=mm;rd.xy*=mm;ro.xz*=mm;rd.xz*=mm;
    float rz=march2(ro,rd,2.5,FAR,j,uTime);
    if(rz>=FAR)continue;
    col=max(col,vmarch(ro+rz*rd,rd,j,bro,uTime));
  }
  ro=bro;rd=brd;vec2 sph=iSphere2(ro,rd);
  if(sph.x>0.0){
    vec3 pos=ro+rd*sph.x,pos2=ro+rd*sph.y;
    vec3 rf=reflect(rd,normalize(pos)),rf2=reflect(rd,normalize(pos2));
    float nz=(-log(abs(flow(rf*1.2,uTime)-0.01)+0.00001));
    float nz2=(-log(abs(flow(rf2*1.2,-uTime)-0.01)+0.00001));
    col+=(0.1*nz*nz*vec3(0.12,0.12,0.5)+0.05*nz2*nz2*vec3(0.55,0.2,0.55))*0.8;
  }
  col*=(1.0+uIntensity*0.6);col=pow(clamp(col,0.0,10.0),vec3(1.5));
  float alpha=clamp(max(col.r,max(col.g,col.b)),0.0,1.0);
  fragColor=vec4(col*1.3,alpha);
}`;

export function PlasmaGlobe({ speed = 1.0, intensity = 1.0, className = "" }: PlasmaGlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mouseRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2", { alpha: true, antialias: true });
    if (!gl) return;
    gl.clearColor(0, 0, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    container.appendChild(canvas);

    const positions = new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);

    const compile = (type: number, src: string) => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, src); gl.compileShader(s); return s;
    };
    const vs = compile(gl.VERTEX_SHADER, VERTEX_SHADER);
    const fs = compile(gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
    const prog = gl.createProgram()!;
    gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
    gl.useProgram(prog);

    const posLoc = gl.getAttribLocation(prog, "position");
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

    const uTime = gl.getUniformLocation(prog, "uTime");
    const uRes = gl.getUniformLocation(prog, "uResolution");
    const uMouse = gl.getUniformLocation(prog, "uMouse");
    const uSpeed = gl.getUniformLocation(prog, "uSpeed");
    const uInt = gl.getUniformLocation(prog, "uIntensity");

    const resize = () => {
      const w = container.offsetWidth, h = container.offsetHeight;
      canvas.width = w; canvas.height = h;
      gl.viewport(0, 0, w, h);
    };
    window.addEventListener("resize", resize); resize();

    const onMouse = (e: MouseEvent) => {
      mouseRef.current.x += (e.clientX - mouseRef.current.x) * 0.08;
      mouseRef.current.y += (e.clientY - mouseRef.current.y) * 0.08;
    };
    window.addEventListener("mousemove", onMouse);

    let raf = 0;
    const loop = (t: number) => {
      raf = requestAnimationFrame(loop);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(uTime, t * 0.001 * speed);
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform2f(uMouse, mouseRef.current.x, mouseRef.current.y);
      gl.uniform1f(uSpeed, speed);
      gl.uniform1f(uInt, intensity);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouse);
      if (canvas.parentNode === container) container.removeChild(canvas);
    };
  }, [speed, intensity]);

  return (
    <div
      ref={containerRef}
      className={`plasma-globe-container ${className}`}
      aria-hidden="true"
    />
  );
}
