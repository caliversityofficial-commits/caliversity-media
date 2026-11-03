"""render.py spec.json  ->  <out>_916.mp4 (+ <out>_45.mp4)
Spec (all times in SOURCE seconds):
{ "input":"raw.mp4", "out":"name", "words":"words.json",
  "tighten":0.3,                  # cut silences longer than this (s); 0 = off. Or give "keep":[[a,b],...]
  "highlight":["imagine","good"],  # words shown in pink gradient (lowercase, no punctuation)
  "red":["bullied"],               # words shown in red
  "replace":{"5":"5"},             # caption text fixes e.g. {"calibacy":"CALIVERSITY"}
  "chunks":[...] optional explicit caption chunks [[startWordIndex,endWordIndexExclusive],...]
  "scenes":[{"type":"bignum|cards|title|list","a":5.5,"b":7.96, ...inner times in source secs ...}],
  "transitions":[1.63,2.6],        # white flash + whoosh + zoom punch
  "cta":{"at":23.0,"text":"TAP BELOW · MESSAGE ME"},
  "music":"song.wav","music_start":7.15,"music_db":-21,
  "formats":["916","45"], "crop45_y":190, "Y":1480, "Y45":1000 }"""
import sys,os,json,re,subprocess,base64,math,time,threading
from concurrent.futures import ThreadPoolExecutor
HERE=os.path.dirname(os.path.abspath(__file__))
spec=json.load(open(sys.argv[1]));BASE=os.path.dirname(os.path.abspath(sys.argv[1]))
P=lambda p:p if os.path.isabs(p) else os.path.join(BASE,p)
T0=time.time();log=lambda *a:print(f'[{time.time()-T0:5.1f}s]',*a,flush=True)
W=json.load(open(P(spec['words'])))
dur=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',P(spec['input'])],capture_output=True,text=True).stdout)
# ---- keep ranges ----
if 'keep' in spec: KEEP=[tuple(k) for k in spec['keep']]
else:
    gap=spec.get('tighten',0.3);KEEP=[];a=0.0
    for i in range(len(W)-1):
        e,s=W[i][1],W[i+1][0]
        if gap and s-e>gap: KEEP.append((a,e+0.08));a=s-0.06
    KEEP.append((a,dur))
def o(t):
    acc=0
    for a,b in KEEP:
        if t<a: return acc
        if t<=b: return acc+t-a
        acc+=b-a
    return acc
OUT=sum(b-a for a,b in KEEP);N=int(OUT*30)
log('keep',KEEP,'len',round(OUT,2))
# ---- captions ----
HL=set(spec.get('highlight',[]));RED=set(spec.get('red',[]));REP={k.lower():v for k,v in spec.get('replace',{}).items()}
clean=lambda w:re.sub(r"[^a-z0-9']","",w.lower())
def cap(w):
    k=clean(w);t=REP.get(k,re.sub(r"[.,!?;:]+$","",w).upper())
    st='r' if k in RED else 'g' if k in HL else 'w';return t,st
if 'chunks' in spec: groups=[list(range(a,b)) for a,b in spec['chunks']]
else:
    groups=[];cur=[]
    for i,w in enumerate(W):
        cur.append(i);nxt=W[i+1] if i+1<len(W) else None
        brk=nxt is None or nxt[0]-w[1]>0.25 or re.search(r'[.?!,]$',w[2]) or len(cur)>=5
        if brk: groups.append(cur);cur=[]
CH=[]
for gi,g in enumerate(groups):
    ws=[[*cap(W[i][2]),round(o(W[i][0]),3)] for i in g]
    n=max(1,math.ceil(len(ws)/3)) if sum(len(t) for t,_,_ in ws)>11 else 1
    per=math.ceil(len(ws)/n);lines=[[[t,tt,st] for t,st,tt in ws[k:k+per]] for k in range(0,len(ws),per)]
    a=round(o(W[g[0]][0]),3);b=round(o(W[groups[gi+1][0]][0]),3) if gi+1<len(groups) else round(OUT,3)
    b=min(b,round(o(W[g[-1]][1])+0.6,3)) if gi+1<len(groups) else b
    CH.append({"a":a,"b":b,"lines":[{"size":(150 if len(L)==1 and len(L[0][0])<=8 else 130 if any(w[2]!='w' for w in L) else 115),"words":L} for L in lines]})
# ---- scenes: convert source times to output times (keys ending in _t or listed) ----
def conv_scene(s):
    s=json.loads(json.dumps(s));a=s['a'];s['a']=round(o(a),3);s['b']=round(o(s['b']),3);s['dur']=s['b']-s['a']
    rel=lambda t:round(o(t)-o(a),3)
    for k in ('at','label_at'):
        if k in s: s[k]=rel(s[k])
    for k in ('top',):
        if k in s: s[k]=[[w,rel(t),st] for w,t,st in s[k]]
    if 'lines' in s:
        s['lines']=[[[w,rel(t),st] for w,t,st in ln] if isinstance(ln,list) else {**ln,'words':[[w,rel(t),st] for w,t,st in ln['words']]} for ln in s['lines']]
    if 'items' in s: s['items']=[[lab,rel(t)] for lab,t in s['items']]
    if 'images' in s:
        for im in s['images']: im['at']=rel(im.get('at',a))
    return s
SC=[conv_scene(s) for s in spec.get('scenes',[])]
FL=[round(o(t),3) for t in spec.get('transitions',[])]
CTA=None
if spec.get('cta'): CTA={**spec['cta'],'at':round(o(spec['cta']['at']),3)}
# images for cards: grab frames
imgs={}
for s in spec.get('scenes',[]):
    for im in s.get('images',[]):
        k=im['key']; f=f'/tmp/_vk_{k}.jpg'
        if 'file' in im: f=P(im['file'])
        else: subprocess.run(['ffmpeg','-v','error','-y','-ss',str(im['frame']),'-i',P(spec['input']),'-frames:v','1','-q:v','2',f],check=True)
        imgs[k]='data:image/jpeg;base64,'+base64.b64encode(open(f,'rb').read()).decode()
SPECJ={"SC":SC,"CH":CH,"CTA":CTA,"FLASH":FL,"Y":spec.get('Y',1480),"Y45":spec.get('Y45',960)}
json.dump(SPECJ,open('/tmp/_vk_spec.json','w'))
FORMATS=spec.get('formats',['916','45'])
WD=f"/tmp/_vk_{spec['out']}";os.makedirs(WD,exist_ok=True)
# ---- base video (trimmed) + audio, in parallel with overlay render ----
def base():
    v=''.join(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[a{i}];" for i,(a,b) in enumerate(KEEP))
    v+=''.join(f"[v{i}][a{i}]" for i in range(len(KEEP)))+f"concat=n={len(KEEP)}:v=1:a=1[cv][ca];[cv]fps=30,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v]"
    subprocess.run(['ffmpeg','-v','error','-y','-i',P(spec['input']),'-filter_complex',v,'-map','[v]','-map','[ca]','-c:v','libx264','-preset','ultrafast','-crf','14','-c:a','pcm_s16le','-ar','48000',f'{WD}/body.mov'],check=True)
    log('base done')
bt=threading.Thread(target=base);bt.start()
# ---- overlays: playwright, 2 workers, dedupe identical frames ----
from playwright.sync_api import sync_playwright
def worker(fmt,idx):
    od=f'{WD}/ov{fmt}';os.makedirs(od,exist_ok=True)
    with sync_playwright() as p:
        b=p.chromium.launch();pg=b.new_page(viewport={"width":1080,"height":1920})
        pg.add_init_script("window.SPEC="+json.dumps(SPECJ))
        pg.goto('file://'+HERE+'/overlay.html');pg.wait_for_timeout(300);pg.evaluate("document.fonts.ready")
        if imgs: pg.evaluate("m=>loadImgs(m)",imgs)
        pg.evaluate(f"setLayout({'true' if fmt=='45' else 'false'})")
        last=None;lastf=None
        for i in idx:
            key=pg.evaluate("t=>draw(t)",i/30)
            fn=f'{od}/{i:05d}.png'
            if key==last and lastf: 
                try: os.link(lastf,fn)
                except FileExistsError: pass
                continue
            u=pg.evaluate("()=>document.getElementById('c').toDataURL('image/png')")
            open(fn,'wb').write(base64.b64decode(u.split(',')[1]));last=key;lastf=fn
        b.close()
jobs=[]
for fmt in FORMATS:
    half=N//2;jobs+= [(fmt,range(0,half)),(fmt,range(half,N))]
with ThreadPoolExecutor(2) as ex: list(ex.map(lambda j:worker(*j),jobs))
log('overlays done');bt.join()
# ---- whoosh ----
import numpy as np,wave
sr=48000;Lw=int(0.28*sr);nz=np.random.default_rng(1).standard_normal(Lw);env=np.sin(np.linspace(0,np.pi,Lw))**2
F=np.fft.rfft(nz*env);fq=np.fft.rfftfreq(Lw,1/sr);F*=np.exp(-((fq-1800)/1500)**2);wh=np.fft.irfft(F,Lw);wh=wh/np.abs(wh).max()*0.18
aw=np.zeros(int((OUT+1)*sr))
for c in FL: st=max(0,int((c-0.12)*sr));aw[st:st+Lw]+=wh[:len(aw)-st]
wv=wave.open(f'{WD}/wh.wav','w');wv.setnchannels(1);wv.setsampwidth(2);wv.setframerate(sr);wv.writeframes((aw.clip(-1,1)*32767).astype(np.int16).tobytes());wv.close()
# zoom punch expression
zexp='1'+''.join(f'+0.16*between(it,{c},{c+0.22})*pow(1-(it-{c})/0.22,3)' for c in FL)
def final(fmt):
    outf=P(f"{spec['out']}_{fmt}.mp4")
    inp=['-i',f'{WD}/body.mov','-framerate','30','-i',f'{WD}/ov{fmt}/%05d.png','-i',f'{WD}/wh.wav']
    vf=f"[0:v]zoompan=z='{zexp}':d=1:x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':s=1080x1920:fps=30[z];" if FL else "[0:v]null[z];"
    if fmt=='45': vf+=f"[z]crop=1080:1350:0:{spec.get('crop45_y',190)}[zc];[zc][1:v]overlay=eof_action=pass,format=yuv420p[v]"
    else: vf+="[z][1:v]overlay=eof_action=pass,format=yuv420p[v]"
    af="[0:a]highpass=f=80,acompressor=threshold=-20dB:ratio=3,loudnorm=I=-14:TP=-1.5,aresample=48000[vo];[2:a]aresample=48000[w]"
    mix="[vo][w]"
    if spec.get('music'):
        inp+=['-i',P(spec['music'])];af+=f";[3:a]atrim=start={spec.get('music_start',0)},asetpts=PTS-STARTPTS,volume={spec.get('music_db',-21)}dB,aresample=48000[m]";mix+="[m]"
    n=mix.count('[')
    af+=f";{mix}amix=inputs={n}:duration=first:normalize=0,alimiter=limit=0.89,aresample=48000,apad[a]"
    subprocess.run(['ffmpeg','-v','error','-y']+inp+['-filter_complex',vf+';'+af,'-map','[v]','-map','[a]','-t',str(OUT),'-c:v','libx264','-preset','veryfast','-b:v','4M','-maxrate','5M','-bufsize','8M','-c:a','aac','-b:a','160k','-movflags','+faststart',outf],check=True)
    log('wrote',outf,os.path.getsize(outf)//1024,'KB')
with ThreadPoolExecutor(2) as ex: list(ex.map(final,FORMATS))
json.dump({"keep":KEEP,"out_len":OUT,"captions":CH},open(P(spec['out']+'_debug.json'),'w'))
log('ALL DONE')
