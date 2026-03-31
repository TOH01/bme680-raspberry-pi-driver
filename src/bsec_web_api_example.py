#!/usr/bin/python3
import argparse
import json
import threading
import time
from pathlib import Path

from flask import Flask, Response

from bsec_bridge import BsecIAQ
from driver import BME680

_DIR   = Path(__file__).parent
LIB    = _DIR / "libbsec_wrapper.so"
STATE  = _DIR / "bsec_state.bin"

_lock   = threading.Lock()
_latest: dict | None = None


def _on_result(result) -> None:
    global _latest
    with _lock:
        _latest = result


app = Flask(__name__)


@app.route("/")
def index():
    return _html


@app.route("/events")
def events():
    def gen():
        while True:
            with _lock:
                d = _latest
            if d is not None:
                yield f"data: {json.dumps(d)}\n\n"
            time.sleep(3)
    return Response(
        gen(),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Air Quality</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#f5f5f3;--sf:#fff;--tx:#1a1a1a;--tx2:#6b6b6b;--tx3:#9a9a9a;
  --bd:rgba(0,0,0,.08);
  --good:#5DCAA5;--warn:#EF9F27;--bad:#E24B4A;
}}
@media(prefers-color-scheme:dark){{:root{{
  --bg:#111;--sf:#1c1c1c;--tx:#e8e8e8;--tx2:#999;--tx3:#666;
  --bd:rgba(255,255,255,.08);
}}}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,sans-serif;
  background:var(--bg);color:var(--tx);font-variant-numeric:tabular-nums}}
@media(min-width:600px){{body{{min-height:100vh;display:flex;
  align-items:center;justify-content:center}}}}
#app{{width:100%;max-width:740px;padding:24px}}
.hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}}
.title{{font-size:15px;font-weight:500;display:flex;align-items:center;gap:8px}}
.sub{{font-size:11px;color:var(--tx3);margin-top:2px}}
.ts{{font-size:10px;color:var(--tx3)}}
.live{{width:7px;height:7px;border-radius:50%;background:var(--good);
  display:inline-block;animation:pulse 2s ease-in-out infinite}}
@keyframes pulse{{50%{{opacity:.4}}}}
.hero{{display:flex;flex-direction:column;align-items:center;padding:16px 0 24px;gap:12px}}
@media(min-width:600px){{.hero{{flex-direction:row;gap:32px;padding:20px 0 28px}}
  .ht{{text-align:left}}}}
.ring{{position:relative;width:150px;height:150px;flex-shrink:0}}
@media(min-width:600px){{.ring{{width:180px;height:180px}}}}
.ring svg{{width:100%;height:100%}}
.rv{{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center}}
.rv span:first-child{{font-size:40px;font-weight:500;line-height:1}}
@media(min-width:600px){{.rv span:first-child{{font-size:48px}}}}
.ru{{font-size:11px;color:var(--tx3);margin-top:3px;letter-spacing:.04em}}
.ht{{text-align:center}}
.hint{{font-size:11px;color:var(--tx3);margin-top:8px;line-height:1.5}}
.cards{{display:flex;flex-direction:column;gap:10px}}
@media(min-width:600px){{.cards{{flex-direction:row;gap:14px}}}}
.card{{background:var(--sf);border-radius:8px;padding:14px 16px;border:.5px solid var(--bd);flex:1}}
@media(min-width:600px){{.card{{padding:16px 20px}}}}
.cl{{font-size:11px;color:var(--tx3);margin-bottom:8px;display:flex;align-items:center;gap:5px}}
.cl svg{{opacity:.45}}
.cr{{display:flex;align-items:center;justify-content:space-between;gap:8px}}
.cv{{font-size:24px;font-weight:500}}
.cu{{font-size:12px;color:var(--tx2)}}
.st{{font-size:11px;color:var(--tx3);display:flex;align-items:center;gap:5px}}
.sd{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.ib{{font-size:12px;font-weight:500;color:var(--tx2);display:flex;align-items:center;gap:6px}}
.foot{{margin-top:20px;padding-top:12px;border-top:.5px solid var(--bd);
  font-size:11px;color:var(--tx3);display:flex;gap:8px;flex-wrap:wrap}}
.sep{{opacity:.3}}
</style>
</head>
<body>
<div id="app"></div>
<script>
var ROOM = {room_json};
var LANG = {{
  en: {{
    title:"Air quality", conn:"connecting\\u2026",
    wait:"Waiting for sensor\\u2026", now:"just now", ago:"s ago",
    temp:"Temperature", hum:"Humidity", co2:"CO\\u2082 equivalent",
    excellent:"Excellent", good:"Good", moderate:"Moderate",
    unhealthy:"Unhealthy", poor:"Poor", hazardous:"Hazardous",
    cold:"Cold", cool:"Cool", comfortable:"Comfortable", warm:"Warm", hot:"Hot",
    vdry:"Very dry", dry:"Dry", sdry:"Slightly dry", optimal:"Optimal",
    shumid:"Slightly humid", humid:"Humid",
    vpoor:"Very poor",
    hExcellent:"Excellent air quality \\u2014 no action needed.",
    hGood:"Air quality is good.",
    hModerate:"Consider ventilating soon.",
    hModHumid:"Moderate air quality and high humidity \\u2014 open a window.",
    hUnhealthy:"Open a window to improve air quality.",
    hPoor:"Ventilate immediately.",
    hHazardous:"Air quality is hazardous \\u2014 ventilate now.",
    hCo2Rising:"Air quality is fine, but CO\\u2082 is rising \\u2014 consider ventilating.",
    hDryAir:"Air quality is good, but humidity is low \\u2014 consider a humidifier.",
    hColdDry:"Room is cool and dry \\u2014 heating and a humidifier would help.",
    hHotHumid:"Room is warm and humid \\u2014 open a window to cool down.",
    hWarm:"Room is warm \\u2014 cracking a window would help.",
    stab:"Stable", stabing:"Stabilizing",
    acc:["Accuracy: unreliable","Accuracy: low","Accuracy: medium","Accuracy: high"],
  }},
  de: {{
    title:"Luftqualit\\u00e4t", conn:"Verbinde\\u2026",
    wait:"Warte auf Sensor\\u2026", now:"gerade eben", ago:"s her",
    temp:"Temperatur", hum:"Luftfeuchtigkeit", co2:"CO\\u2082-\\u00c4quivalent",
    excellent:"Ausgezeichnet", good:"Gut", moderate:"M\\u00e4\\u00dfig",
    unhealthy:"Ungesund", poor:"Schlecht", hazardous:"Gef\\u00e4hrlich",
    cold:"Kalt", cool:"K\\u00fchl", comfortable:"Angenehm", warm:"Warm", hot:"Hei\\u00df",
    vdry:"Sehr trocken", dry:"Trocken", sdry:"Leicht trocken", optimal:"Optimal",
    shumid:"Leicht feucht", humid:"Feucht",
    vpoor:"Sehr schlecht",
    hExcellent:"Ausgezeichnete Luftqualit\\u00e4t \\u2014 kein Handlungsbedarf.",
    hGood:"Luftqualit\\u00e4t ist gut.",
    hModerate:"L\\u00fcften empfohlen.",
    hModHumid:"M\\u00e4\\u00dfige Luftqualit\\u00e4t und hohe Luftfeuchtigkeit \\u2014 Fenster \\u00f6ffnen.",
    hUnhealthy:"Fenster \\u00f6ffnen, um die Luftqualit\\u00e4t zu verbessern.",
    hPoor:"Sofort l\\u00fcften.",
    hHazardous:"Luftqualit\\u00e4t ist gef\\u00e4hrlich \\u2014 sofort l\\u00fcften.",
    hCo2Rising:"Luftqualit\\u00e4t ist gut, aber CO\\u2082 steigt \\u2014 ggf. l\\u00fcften.",
    hDryAir:"Luftqualit\\u00e4t ist gut, aber die Luft ist trocken \\u2014 Luftbefeuchter empfohlen.",
    hColdDry:"Raum ist k\\u00fchl und trocken \\u2014 Heizung und Luftbefeuchter helfen.",
    hHotHumid:"Raum ist warm und feucht \\u2014 Fenster \\u00f6ffnen.",
    hWarm:"Raum ist warm \\u2014 Fenster einen Spalt \\u00f6ffnen empfohlen.",
    stab:"Stabil", stabing:"Stabilisiert",
    acc:["Genauigkeit: unzuverl\\u00e4ssig","Genauigkeit: niedrig","Genauigkeit: mittel","Genauigkeit: hoch"],
  }}
}};
var L = LANG[navigator.language.slice(0,2)] || LANG.en;

var CIRC = 2 * Math.PI * 76;

var IAQ_LEVELS = [
  [50,  L.excellent,"good"],[100,L.good,"good"],
  [150, L.moderate,"warn"],[200,L.unhealthy,"warn"],
  [300, L.poor,"bad"],[Infinity,L.hazardous,"bad"],
];

var CARDS = [
  {{id:"temp",key:"temperature",label:L.temp,unit:"\\u00b0C",fix:1,
   icon:'<path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>',
   rate:function(v){{
     if(v<16)return[L.cold,"bad"];
     if(v<18)return[L.cool,"warn"];
     if(v<=22)return[L.comfortable,"good"];
     if(v<=26)return[L.warm,"warn"];
     return[L.hot,"bad"];
   }}}},
  {{id:"hum",key:"humidity",label:L.hum,unit:"%",fix:1,
   icon:'<path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>',
   rate:function(v){{
     if(v<20)return[L.vdry,"bad"];
     if(v<35)return[L.dry,"warn"];
     if(v<40)return[L.sdry,"warn"];
     if(v<=60)return[L.optimal,"good"];
     if(v<=70)return[L.shumid,"warn"];
     return[L.humid,"bad"];
   }}}},
  {{id:"co2",key:"co2_equivalent",label:L.co2,unit:"ppm",fix:0,
   icon:'<circle cx="12" cy="12" r="9"/>',
   rate:function(v){{
      if(v<800)return[L.excellent,"good"];
      if(v<1200)return[L.good,"good"];
      if(v<2000)return[L.moderate,"warn"];
      if(v<3000)return[L.poor,"bad"];
      return[L.vpoor,"bad"];
   }}}},
];

function rateIAQ(v){{
  for(var i=0;i<IAQ_LEVELS.length;i++)
    if(v<=IAQ_LEVELS[i][0])return IAQ_LEVELS[i].slice(1);
}}

var _buf=[];
function smooth(v){{
  _buf.push(v);if(_buf.length>3)_buf.shift();
  return _buf.reduce(function(a,b){{return a+b}})/_buf.length;
}}

function mkHint(d,iaq){{
  var co2=d.co2_equivalent,hum=d.humidity,tmp=d.temperature;
  if(iaq>300||co2>3500)return L.hHazardous;
  if(iaq>200||co2>2500)return L.hPoor;
  if(iaq>150||co2>2000)return hum>70?L.hModHumid:L.hUnhealthy;
  if(iaq>100||co2>1500)return hum>70?L.hModHumid:L.hModerate;
  if(co2>1200)return L.hCo2Rising;
  if(hum<25&&tmp<18)return L.hColdDry;
  if(hum<35)return L.hDryAir;
  if(hum>70&&tmp>24)return L.hHotHumid;
  if(tmp>26)return L.hWarm;
  if(co2>800)return L.hCo2Rising;
  return iaq<=50?L.hExcellent:L.hGood;
}}

function h(tag,cls,html){{
  var e=document.createElement(tag);
  if(cls)e.className=cls;if(html)e.innerHTML=html;return e;
}}

function ico(d){{
  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '+
    'stroke="currentColor" stroke-width="2" stroke-linecap="round">'+d+'</svg>';
}}

function mkRing(){{
  var w=h("div","ring");
  w.innerHTML=
    '<svg viewBox="0 0 180 180">'+
    '<circle cx="90" cy="90" r="76" fill="none" stroke="var(--bd)" stroke-width="5" opacity=".25"/>'+
    '<circle id="arc" cx="90" cy="90" r="76" fill="none" stroke-width="5" '+
      'stroke-dasharray="'+CIRC+'" stroke-dashoffset="'+CIRC+'" stroke-linecap="round" '+
      'transform="rotate(-90 90 90)" style="transition:stroke-dashoffset 1s,stroke .5s"/>'+
    '</svg>'+
    '<div class="rv"><span id="inum">--</span><span class="ru">IAQ</span></div>';
  return w;
}}

function mkCard(c){{
  return h("div","card",
    '<div class="cl">'+ico(c.icon)+' '+c.label+'</div>'+
    '<div class="cr"><div><span id="'+c.id+'v" class="cv">--</span>'+
    '<span class="cu"> '+c.unit+'</span></div>'+
    '<span class="st" id="'+c.id+'s"><span class="sd"></span><span></span></span></div>');
}}

var lastUp=0;

function update(d){{
  var iaq=smooth(d.iaq),r=rateIAQ(iaq);
  document.getElementById("inum").textContent=Math.round(iaq);
  var arc=document.getElementById("arc");
  arc.setAttribute("stroke-dashoffset",CIRC-Math.min(CIRC,(iaq/500)*CIRC));
  arc.setAttribute("stroke","var(--"+r[1]+")");
  document.getElementById("ibdot").style.background="var(--"+r[1]+")";
  document.getElementById("ibtx").textContent=r[0];
  document.getElementById("hint").textContent=mkHint(d,iaq);
  CARDS.forEach(function(c){{
    document.getElementById(c.id+"v").textContent=d[c.key].toFixed(c.fix);
    var cr=c.rate(d[c.key]),el=document.getElementById(c.id+"s");
    el.children[0].style.background="var(--"+cr[1]+")";
    el.children[1].textContent=cr[0];
  }});
  document.getElementById("fstab").textContent=d.stab_status?L.stab:L.stabing;
  document.getElementById("facc").textContent=L.acc[d.iaq_accuracy]||L.acc[0];
  lastUp=Date.now();
}}

var root=document.getElementById("app");

root.innerHTML=
  '<div class="hdr"><div><div class="title"><span class="live"></span>'+L.title+'</div>'+
  '<div class="sub">'+ROOM+'</div></div><span class="ts" id="ts">'+L.conn+'</span></div>';

var hero=h("div","hero");
hero.appendChild(mkRing());
hero.appendChild(h("div","ht",
  '<div class="ib"><span class="sd" id="ibdot"></span><span id="ibtx">--</span></div>'+
  '<div class="hint" id="hint">'+L.wait+'</div>'));
root.appendChild(hero);

var cg=h("div","cards");
CARDS.forEach(function(c){{cg.appendChild(mkCard(c))}});
root.appendChild(cg);

root.insertAdjacentHTML("beforeend",
  '<div class="foot"><span id="fstab">--</span><span class="sep">\\u00b7</span>'+
  '<span id="facc">--</span><span class="sep">\\u00b7</span><span>BME680</span></div>');

var es=new EventSource("/events");
es.onmessage=function(e){{update(JSON.parse(e.data))}};
es.onerror=function(){{document.getElementById("ts").textContent=L.conn}};
setInterval(function(){{
  if(!lastUp)return;
  var s=Math.round((Date.now()-lastUp)/1000);
  document.getElementById("ts").textContent=s<5?L.now:s+L.ago;
}},1000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BME680 air-quality dashboard")
    parser.add_argument(
        "--room", "-r",
        default="Living room",
        help="Room name shown in the dashboard (default: Living room)",
    )
    args = parser.parse_args()

    _html = _HTML_TEMPLATE.format(room_json=json.dumps(args.room))

    bme  = BME680()
    bsec = BsecIAQ(lib_path=LIB)
    threading.Thread(
        target=bsec.run, args=(bme, _on_result),
        kwargs={"state_path": STATE}, daemon=True,
    ).start()
    try:
        app.run(host="0.0.0.0", port=8080, threaded=True, ssl_context="adhoc")
    except KeyboardInterrupt:
        bsec.save_state(STATE)
    finally:
        bme.close()
