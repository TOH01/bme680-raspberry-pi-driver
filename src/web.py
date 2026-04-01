#!/usr/bin/python3
"""
Air-quality web server.

Serves:
  /              Live dashboard (SSE-driven, original design)
  /events        Server-Sent Events from latest.json
  /history       History dashboard (chart + stats)
  /history/data  JSON API for historical data from airquality.bin

Runs as a standalone systemd service, fully independent of sensor.py.
Detects sensor staleness by checking the timestamp in latest.json.
"""

import argparse
import json
import time
from pathlib import Path

from flask import Flask, Response, request

from datalogger import DataLogger

_DIR = Path(__file__).parent
LOG = _DIR / "airquality.bin"
LATEST = _DIR / "latest.json"

app = Flask(__name__)
_logger: DataLogger | None = None
_html: str = ""
_history_html: str = ""


# ── helpers ──────────────────────────────────────────────────────

def _read_latest() -> dict | None:
    """Read the latest sensor reading written by sensor.py."""
    try:
        return json.loads(LATEST.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# ── routes ───────────────────────────────────────────────────────

@app.route("/")
def index():
    return _html


@app.route("/events")
def events():
    """SSE stream.  Reads latest.json every 3 s.  Adds _stale flag
    so the dashboard can show a warning if the sensor is down."""
    def gen():
        last_sent = None
        while True:
            d = _read_latest()
            if d is not None:
                ts = d.get("timestamp", 0)
                stale = (time.time() - ts) > 90
                d["_stale"] = stale
                payload = json.dumps(d)
                if payload != last_sent:
                    yield f"data: {payload}\n\n"
                    last_sent = payload
            time.sleep(3)
    return Response(
        gen(),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/history")
def history():
    return _history_html


@app.route("/history/data")
def history_data():
    r = request.args.get("range", "day")
    if r not in ("day", "week", "month", "year"):
        r = "day"
    return Response(
        json.dumps(_logger.query(r)),
        content_type="application/json",
    )


_LIVE_TEMPLATE = """\
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
.offline{{background:var(--bad);animation:none}}
@keyframes pulse{{50%{{opacity:.4}}}}
.nav{{font-size:12px;color:var(--tx3);text-decoration:none;display:flex;align-items:center;gap:4px}}
.nav:hover{{color:var(--tx2)}}
.nav svg{{width:14px;height:14px}}
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
    vpoor:"Very poor", offline:"Sensor offline",
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
    stab:"Stable", stabing:"Stabilizing", hist:"History",
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
    vpoor:"Sehr schlecht", offline:"Sensor offline",
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
    stab:"Stabil", stabing:"Stabilisiert", hist:"Verlauf",
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
  /* handle stale / offline */
  var dot=document.getElementById("livedot");
  if(d._stale){{
    dot.className="live offline";
    document.getElementById("ts").textContent=L.offline;
    return;
  }}
  dot.className="live";

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
  '<div class="hdr"><div><div class="title"><span class="live" id="livedot"></span>'+L.title+'</div>'+
  '<div class="sub">'+ROOM+'</div></div>'+
  '<a class="nav" href="/history">'+L.hist+
  ' <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'+
  '<path d="M5 12h14M12 5l7 7-7 7"/></svg></a></div>';

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
  '<span id="facc">--</span><span class="sep">\\u00b7</span><span>BME680</span>'+
  '<span class="sep">\\u00b7</span><span class="ts" id="ts">'+L.conn+'</span></div>');

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


_HISTORY_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Air Quality \u2014 History</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#f5f5f3;--sf:#fff;--tx:#1a1a1a;--tx2:#6b6b6b;--tx3:#9a9a9a;
  --bd:rgba(0,0,0,.08);
  --good:#5DCAA5;--warn:#EF9F27;--bad:#E24B4A;
  --blue:#4BA3E2;
}}
@media(prefers-color-scheme:dark){{:root{{
  --bg:#111;--sf:#1c1c1c;--tx:#e8e8e8;--tx2:#999;--tx3:#666;
  --bd:rgba(255,255,255,.08);
}}}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,sans-serif;
  background:var(--bg);color:var(--tx);font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased}}
@media(min-width:600px){{body{{min-height:100vh;display:flex;
  align-items:center;justify-content:center}}}}
#app{{width:100%;max-width:740px;padding:24px}}
.hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}}
.title{{font-size:15px;font-weight:500}}
.sub{{font-size:11px;color:var(--tx3);margin-top:2px}}
.back{{font-size:12px;color:var(--tx3);text-decoration:none;display:flex;align-items:center;gap:4px}}
.back:hover{{color:var(--tx2)}}
.back svg{{width:14px;height:14px}}
.metrics{{display:flex;gap:20px;margin-bottom:14px;border-bottom:.5px solid var(--bd);padding-bottom:0}}
@media(max-width:599px){{.metrics{{gap:16px}}}}
.met{{font-size:12px;padding:0 0 10px;border:none;background:none;
  color:var(--tx3);cursor:pointer;font-family:inherit;font-weight:500;
  position:relative;transition:color .2s;display:flex;align-items:center;gap:5px}}
.met:hover{{color:var(--tx2)}}
.met.on{{color:var(--tx)}}
.met::after{{content:"";position:absolute;bottom:-0.5px;left:0;right:0;
  height:2px;border-radius:1px;background:transparent;transition:background .2s}}
.met.on::after{{background:var(--accent)}}
.met svg{{width:14px;height:14px;opacity:.45}}
.met.on svg{{opacity:.7}}
.ranges{{display:flex;gap:2px;margin-bottom:16px;
  background:var(--sf);border-radius:8px;border:.5px solid var(--bd);
  padding:3px;width:fit-content}}
.rng{{font-size:11px;padding:5px 16px;border-radius:6px;border:none;
  background:transparent;color:var(--tx3);cursor:pointer;font-family:inherit;
  font-weight:500;transition:all .2s}}
.rng.on{{background:var(--bg);color:var(--tx)}}
.chart-wrap{{background:var(--sf);border-radius:10px;border:.5px solid var(--bd);
  padding:16px 16px 12px;margin-bottom:14px;position:relative}}
canvas{{width:100%;height:220px;display:block}}
@media(min-width:600px){{canvas{{height:280px}}}}
.tip{{position:absolute;pointer-events:none;opacity:0;transition:opacity .15s;
  background:var(--sf);border:.5px solid var(--bd);border-radius:8px;
  padding:8px 12px;box-shadow:0 4px 12px rgba(0,0,0,.08);z-index:10}}
.tip-val{{font-size:15px;font-weight:500}}
.tip-unit{{font-size:11px;color:var(--tx2);margin-left:2px}}
.tip-time{{font-size:10px;color:var(--tx3);margin-top:2px}}
.cards{{display:flex;flex-direction:column;gap:10px}}
@media(min-width:600px){{.cards{{flex-direction:row;gap:14px}}}}
.card{{background:var(--sf);border-radius:8px;padding:14px 16px;
  border:.5px solid var(--bd);flex:1}}
@media(min-width:600px){{.card{{padding:16px 20px}}}}
.cl{{font-size:11px;color:var(--tx3);margin-bottom:8px;display:flex;align-items:center;gap:5px}}
.cl svg{{opacity:.45}}
.cr{{display:flex;align-items:center;justify-content:space-between;gap:8px}}
.cv{{font-size:24px;font-weight:500}}
.cu{{font-size:12px;color:var(--tx2)}}
.st{{font-size:11px;color:var(--tx3);display:flex;align-items:center;gap:5px}}
.sd{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.foot{{margin-top:20px;padding-top:12px;border-top:.5px solid var(--bd);
  font-size:11px;color:var(--tx3);display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.sep{{opacity:.3}}
.status-dot{{width:6px;height:6px;border-radius:50%;display:inline-block}}
.empty{{text-align:center;padding:48px 0;color:var(--tx3);font-size:12px}}
</style>
</head>
<body>
<div id="app">
  <div class="hdr">
    <div>
      <div class="title">{room_esc}</div>
      <div class="sub">History</div>
    </div>
    <a class="back" href="/">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
      Live
    </a>
  </div>
  <div class="metrics" id="metrics"></div>
  <div class="ranges" id="ranges"></div>
  <div class="chart-wrap">
    <canvas id="cv"></canvas>
    <div class="tip" id="tip">
      <div><span class="tip-val" id="tipv"></span><span class="tip-unit" id="tipu"></span></div>
      <div class="tip-time" id="tipt"></div>
    </div>
  </div>
  <div class="cards" id="stats"></div>
  <div class="foot">
    <span class="status-dot" id="fdot"></span>
    <span id="flast"></span>
    <span class="sep">&middot;</span>
    <span id="fcount"></span>
    <span class="sep">&middot;</span>
    <span>30 s intervals</span>
    <span class="sep">&middot;</span>
    <span>BME680</span>
  </div>
</div>

<script>
(function(){{

var ICONS = {{
  iaq:  '<path d="M3 12h4l3-9 4 18 3-9h4"/>',
  temp: '<path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>',
  hum:  '<path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/>',
  co2:  '<circle cx="12" cy="12" r="9"/>',
}};
function ico(d){{
  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '+
    'stroke="currentColor" stroke-width="2" stroke-linecap="round">'+d+'</svg>';
}}

var METRICS = [
  {{k:"i", l:"IAQ",      icon:ICONS.iaq,  unit:"",     color:"#5DCAA5", fix:0,
   thresholds:[
     {{v:50,  label:"Good",     s:"good"}},
     {{v:100, label:"Moderate",  s:"warn"}},
     {{v:150, label:"Unhealthy", s:"warn"}},
     {{v:300, label:"Poor",      s:"bad"}},
   ],
   rate:function(v){{
     if(v<=50) return["Excellent","good"];if(v<=100)return["Good","good"];
     if(v<=150)return["Moderate","warn"];if(v<=200)return["Unhealthy","warn"];
     if(v<=300)return["Poor","bad"];return["Hazardous","bad"];
   }}}},
  {{k:"t", l:"Temp",     icon:ICONS.temp, unit:"\\u00b0C", color:"#EF9F27", fix:1,
   thresholds:[
     {{v:18, label:"Cool",  s:"warn"}},
     {{v:22, label:"",      s:"good"}},
     {{v:26, label:"Warm",  s:"warn"}},
   ],
   rate:function(v){{
     if(v<16)return["Cold","bad"];if(v<18)return["Cool","warn"];
     if(v<=22)return["Comfortable","good"];if(v<=26)return["Warm","warn"];
     return["Hot","bad"];
   }}}},
  {{k:"h", l:"Humidity", icon:ICONS.hum,  unit:"%",    color:"#4BA3E2", fix:1,
   thresholds:[
     {{v:35, label:"Dry",     s:"warn"}},
     {{v:40, label:"",        s:"good"}},
     {{v:60, label:"",        s:"good"}},
     {{v:70, label:"Humid",   s:"warn"}},
   ],
   rate:function(v){{
     if(v<20)return["Very dry","bad"];if(v<35)return["Dry","warn"];
     if(v<40)return["Slightly dry","warn"];if(v<=60)return["Optimal","good"];
     if(v<=70)return["Slightly humid","warn"];return["Humid","bad"];
   }}}},
  {{k:"c", l:"CO\\u2082",  icon:ICONS.co2,  unit:"ppm",  color:"#E24B4A", fix:0,
   thresholds:[
     {{v:800,  label:"Good",     s:"good"}},
     {{v:1200, label:"Moderate",  s:"warn"}},
     {{v:2000, label:"Poor",      s:"bad"}},
   ],
   rate:function(v){{
     if(v<800)return["Excellent","good"];if(v<1200)return["Good","good"];
     if(v<2000)return["Moderate","warn"];if(v<3000)return["Poor","bad"];
     return["Very poor","bad"];
   }}}},
];

var RANGES = [
  {{k:"day",l:"24 h"}},{{k:"week",l:"7 d"}},{{k:"month",l:"30 d"}},{{k:"year",l:"1 y"}},
];

var metric=0, range="day", cache={{}}, data_=null;

var cv=document.getElementById("cv"), ctx=cv.getContext("2d");
var dpr=window.devicePixelRatio||1;
var tip=document.getElementById("tip");

function resize(){{
  var r=cv.getBoundingClientRect();
  cv.width=r.width*dpr; cv.height=r.height*dpr;
  ctx.setTransform(dpr,0,0,dpr,0,0);
}}

/* tabs */
var md=document.getElementById("metrics");
METRICS.forEach(function(m,i){{
  var b=document.createElement("button");
  b.className="met"; b.innerHTML=ico(m.icon)+" "+m.l;
  b.onclick=function(){{metric=i;render()}};
  md.appendChild(b);
}});
var rd=document.getElementById("ranges");
RANGES.forEach(function(r){{
  var b=document.createElement("button");
  b.className="rng";b.textContent=r.l;b.dataset.k=r.k;
  b.onclick=function(){{range=r.k;load()}};
  rd.appendChild(b);
}});

function updTabs(){{
  [].forEach.call(md.children,function(b,i){{
    b.className="met"+(i===metric?" on":"");
    b.style.setProperty("--accent",METRICS[i].color);
  }});
  [].forEach.call(rd.children,function(b){{
    b.className="rng"+(b.dataset.k===range?" on":"");
  }});
}}

function getCSS(v){{return getComputedStyle(document.documentElement).getPropertyValue(v).trim()}}

/* ── chart ────────────────────────────── */
function draw(){{
  var w=cv.width/dpr, ht=cv.height/dpr;
  ctx.clearRect(0,0,w,ht);
  if(!data_||!data_.points||data_.points.length<2){{
    ctx.fillStyle=getCSS("--tx3");ctx.font="12px -apple-system,sans-serif";
    ctx.textAlign="center";ctx.fillText("No data for this range",w/2,ht/2);
    return;
  }}

  var m=METRICS[metric],pts=data_.points,key=m.k;
  var vals=pts.map(function(p){{return p[key]}});
  var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals);
  var margin=(mx-mn)*0.12||5; mn-=margin; mx+=margin;

  m.thresholds.forEach(function(th){{
    if(th.v<mx+margin&&th.v>mn-margin){{
      if(th.v>mx)mx=th.v+margin*0.5;
      if(th.v<mn)mn=th.v-margin*0.5;
    }}
  }});

  var pad={{t:12,b:28,l:44,r:50}};
  var cw=w-pad.l-pad.r, ch=ht-pad.t-pad.b;
  var tx3=getCSS("--tx3"),bd=getCSS("--bd");
  var colorMap={{good:getCSS("--good"),warn:getCSS("--warn"),bad:getCSS("--bad")}};

  /* grid */
  ctx.lineWidth=0.5;
  for(var g=0;g<=4;g++){{
    var gy=pad.t+ch*(1-g/4);
    ctx.strokeStyle=bd;
    ctx.beginPath();ctx.moveTo(pad.l,gy);ctx.lineTo(pad.l+cw,gy);ctx.stroke();
    ctx.fillStyle=tx3;ctx.font="10px -apple-system,sans-serif";ctx.textAlign="right";
    ctx.fillText((mn+(mx-mn)*(g/4)).toFixed(m.fix),pad.l-8,gy+3);
  }}

  /* threshold lines */
  m.thresholds.forEach(function(th){{
    if(th.v<=mn||th.v>=mx)return;
    var ty=pad.t+ch*(1-(th.v-mn)/(mx-mn));
    ctx.strokeStyle=colorMap[th.s];ctx.globalAlpha=0.35;ctx.lineWidth=1;
    ctx.setLineDash([4,4]);
    ctx.beginPath();ctx.moveTo(pad.l,ty);ctx.lineTo(pad.l+cw,ty);ctx.stroke();
    ctx.setLineDash([]);ctx.globalAlpha=1;
    if(th.label){{
      ctx.font="9px -apple-system,sans-serif";ctx.textAlign="left";
      ctx.fillStyle=colorMap[th.s];ctx.globalAlpha=0.6;
      ctx.fillText(th.label,pad.l+cw+6,ty+3);ctx.globalAlpha=1;
    }}
  }});

  /* time labels */
  ctx.fillStyle=tx3;ctx.font="10px -apple-system,sans-serif";ctx.textAlign="center";
  var ticks=w<500?4:6;
  for(var ti=0;ti<ticks;ti++){{
    var idx=Math.round(ti*(pts.length-1)/(ticks-1));
    var tx_=pad.l+cw*(idx/(pts.length-1));
    var d=new Date(pts[idx].ts*1000),lb;
    if(range==="day")lb=d.getHours()+":00";
    else if(range==="week")lb=["So","Mo","Di","Mi","Do","Fr","Sa"][d.getDay()];
    else if(range==="month")lb=d.getDate()+"."+(d.getMonth()+1)+".";
    else lb=["Jan","Feb","M\\u00e4r","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"][d.getMonth()];
    ctx.fillText(lb,tx_,ht-8);
  }}

  /* line */
  ctx.beginPath();
  for(var j=0;j<pts.length;j++){{
    var px=pad.l+cw*(j/(pts.length-1));
    var py=pad.t+ch*(1-(vals[j]-mn)/(mx-mn));
    j===0?ctx.moveTo(px,py):ctx.lineTo(px,py);
  }}
  ctx.strokeStyle=m.color;ctx.lineWidth=1.5;ctx.lineJoin="round";ctx.stroke();
  ctx.lineTo(pad.l+cw,pad.t+ch);ctx.lineTo(pad.l,pad.t+ch);ctx.closePath();
  var grd=ctx.createLinearGradient(0,pad.t,0,pad.t+ch);
  grd.addColorStop(0,m.color+"20");grd.addColorStop(1,m.color+"00");
  ctx.fillStyle=grd;ctx.fill();

  cv._meta={{pad:pad,cw:cw,ch:ch,mn:mn,mx:mx,pts:pts,key:key,m:m,vals:vals}};
}}

/* tooltip */
function showTip(cx){{
  var meta=cv._meta;if(!meta)return;
  var rect=cv.getBoundingClientRect(),x=cx-rect.left;
  var rel=(x-meta.pad.l)/meta.cw;
  if(rel<0||rel>1){{tip.style.opacity=0;return}}
  var idx=Math.round(rel*(meta.pts.length-1));
  var pt=meta.pts[idx],val=meta.vals[idx],m=meta.m;
  document.getElementById("tipv").textContent=val.toFixed(m.fix);
  document.getElementById("tipu").textContent=" "+m.unit;
  var d=new Date(pt.ts*1000),p2=function(n){{return n<10?"0"+n:""+n}};
  document.getElementById("tipt").textContent=
    p2(d.getDate())+"."+p2(d.getMonth()+1)+" "+p2(d.getHours())+":"+p2(d.getMinutes());
  var tipW=110,tipH=48,left=x-tipW/2;
  if(left<4)left=4;if(left+tipW>rect.width-4)left=rect.width-tipW-4;
  var py=meta.pad.t+meta.ch*(1-(val-meta.mn)/(meta.mx-meta.mn));
  var top=py-tipH-12;if(top<0)top=py+12;
  tip.style.left=left+"px";tip.style.top=top+"px";tip.style.opacity=1;
  draw();
  var px=meta.pad.l+meta.cw*(idx/(meta.pts.length-1));
  ctx.strokeStyle=getCSS("--tx3");ctx.globalAlpha=0.3;ctx.lineWidth=1;
  ctx.setLineDash([3,3]);ctx.beginPath();
  ctx.moveTo(px,meta.pad.t);ctx.lineTo(px,meta.pad.t+meta.ch);ctx.stroke();
  ctx.setLineDash([]);ctx.globalAlpha=1;
  ctx.beginPath();ctx.arc(px,py,4,0,Math.PI*2);
  ctx.fillStyle=m.color;ctx.fill();
  ctx.strokeStyle=getCSS("--sf");ctx.lineWidth=2;ctx.stroke();
}}
cv.addEventListener("mousemove",function(e){{showTip(e.clientX)}});
cv.addEventListener("mouseleave",function(){{tip.style.opacity=0;draw()}});
cv.addEventListener("touchmove",function(e){{e.preventDefault();showTip(e.touches[0].clientX)}},{{passive:false}});
cv.addEventListener("touchend",function(){{tip.style.opacity=0;draw()}});

/* stats cards */
function updStats(){{
  var sd=document.getElementById("stats");sd.innerHTML="";
  if(!data_||!data_.stats)return;
  var m=METRICS[metric],s=data_.stats[m.k];if(!s)return;
  var colorMap={{good:getCSS("--good"),warn:getCSS("--warn"),bad:getCSS("--bad")}};
  [["Minimum",s.min],["Average",s.avg],["Maximum",s.max]].forEach(function(x){{
    var rating=m.rate(x[1]);
    var c=document.createElement("div");c.className="card";
    c.innerHTML='<div class="cl">'+ico(m.icon)+' '+x[0]+'</div>'+
      '<div class="cr"><div><span class="cv">'+x[1].toFixed(m.fix)+'</span>'+
      '<span class="cu"> '+m.unit+'</span></div>'+
      '<span class="st"><span class="sd" style="background:'+colorMap[rating[1]]+'"></span>'+
      '<span>'+rating[0]+'</span></span></div>';
    sd.appendChild(c);
  }});
}}

function updFooter(){{
  if(!data_)return;
  var n=data_.count||0;
  document.getElementById("fcount").textContent=n.toLocaleString()+" records";
  /* check freshness of latest record */
  var pts=data_.points;
  if(pts&&pts.length){{
    var last=pts[pts.length-1].ts;
    var ago=Math.round(Date.now()/1000-last);
    var dot=document.getElementById("fdot");
    if(ago>120){{
      dot.style.background=getCSS("--bad");
      document.getElementById("flast").textContent="Sensor offline";
    }} else {{
      dot.style.background=getCSS("--good");
      if(ago<60) document.getElementById("flast").textContent="Last recorded "+ago+" s ago";
      else document.getElementById("flast").textContent="Last recorded "+Math.round(ago/60)+" min ago";
    }}
  }}
}}

function render(){{updTabs();resize();draw();updStats();updFooter()}}

function load(){{
  if(cache[range]){{data_=cache[range];render();return}}
  data_=null;render();
  fetch("/history/data?range="+range)
    .then(function(r){{return r.json()}})
    .then(function(d){{cache[range]=d;data_=d;render()}})
    .catch(function(){{data_={{points:[],stats:{{}},count:0}};render()}});
}}

window.addEventListener("resize",render);
if(window.matchMedia)
  window.matchMedia("(prefers-color-scheme:dark)").addEventListener("change",function(){{setTimeout(render,50)}});

load();

}})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BME680 air-quality web server")
    parser.add_argument(
        "--room", "-r",
        default="Living room",
        help="Room name shown in both dashboards (default: Living room)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int, default=8080,
        help="HTTP port (default: 8080)",
    )
    args = parser.parse_args()

    _html = _LIVE_TEMPLATE.format(room_json=json.dumps(args.room))
    _history_html = _HISTORY_TEMPLATE.format(room_esc=args.room)
    _logger = DataLogger(LOG)

    print(f"[web] serving on https://0.0.0.0:{args.port}")
    app.run(
        host="0.0.0.0",
        port=args.port,
        threaded=True,
        ssl_context="adhoc",
    )
