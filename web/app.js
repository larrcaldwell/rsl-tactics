(function () {
  "use strict";
  var Q = new URLSearchParams(location.search);
  var DEMO = Q.get("demo") === "1";
  var BASE = DEMO ? "demo-data/" : "data/";
  var G = window.GLOSSARY || {};
  var S = { prof: null, mu: null, ht: null, live: null, health: null, sched: null };

  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var fmt = function (v, d) { return v == null ? "n/a" : Number(v).toFixed(d == null ? 1 : d); };

  function getJSON(name) {
    return fetch(BASE + name + "?t=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function ago(iso) {
    if (!iso) return "never";
    var m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (m < 1) return "just now"; if (m < 60) return m + " min ago";
    var h = Math.round(m / 60); if (h < 48) return h + " h ago";
    return Math.round(h / 24) + " d ago";
  }

  /* ---------- glossary sheet ---------- */
  function openSheet(html) { $("sheet").innerHTML = '<span class="x" id="sx">&times;</span>' + html; $("sheet").style.display = "block"; $("sbg").style.display = "block"; $("sx").onclick = closeSheet; }
  function closeSheet() { $("sheet").style.display = "none"; $("sbg").style.display = "none"; }
  $("sbg").onclick = closeSheet;
  function learn(term) {
    var g = G[term]; if (!g) return;
    openSheet("<h3>" + esc(g.name) + "</h3><p>" + esc(g.short) + '</p><div class="row w"><div class="k">Why it matters</div><div class="v">' + esc(g.why) + "</div></div>");
  }
  window.__learn = learn;
  var L = function (term, text) { return '<span class="link" onclick="__learn(\'' + term + '\')">' + esc(text) + "</span>"; };

  /* ---------- cards ---------- */
  function card(c, opp) {
    if (opp === undefined) opp = !/^RSL\b/.test(c.title);
    var m = c.confidence === "Measured";
    var nums = (c.numbers || []).map(function (n) {
      return "<tr><td>" + esc(n.team) + "</td><td>" + L(n.term, n.label) + '</td><td class="n">' + fmt(n.value, 2) + '</td><td class="n">' + esc(n.rank || "") + "</td></tr>";
    }).join("");
    return '<div class="card' + (opp ? " opp" : "") + '"><div class="top"><h3>' + esc(c.title) + '</h3><span class="badge ' + (m ? "m" : "i") + '" onclick="__learn(\'' + (m ? "measured" : "inference") + '\')">' + (m ? "MEASURED" : "INFERENCE") + "</span></div>" +
      '<div class="row d"><div class="k">Data</div><div class="v">' + esc(c.data) + "</div></div>" +
      '<div class="row m"><div class="k">Meaning</div><div class="v">' + esc(c.meaning) + "</div></div>" +
      '<div class="row w"><div class="k">Watch for</div><div class="v">' + esc(c.watch) + "</div></div>" +
      "<details><summary>Show the numbers and the rule</summary>" +
      (nums ? '<table><tr><th>Team</th><th>Stat</th><th class="n">Value</th><th class="n">Rank</th></tr>' + nums + "</table>" : '<div class="small">This card uses game state or score, not a season stat.</div>') +
      '<div class="rule">Rule: ' + esc(c.rule) + "</div></details></div>";
  }
  function cards(list, opp, cap) { return (list || []).slice(0, cap || 99).map(function (c) { return card(c, opp); }).join(""); }

  /* ---------- pitch (attack zones) ---------- */
  function pitch(as, color) {
    if (!as || as.left_pct == null) return "";
    var L_ = as.left_pct, C = as.center_pct, R = as.right_pct, w = 200, h = 130;
    function col(x, p, lab) { var o = (0.15 + (p / 100) * 0.75).toFixed(2); return '<rect x="' + x + '" y="0" width="' + (w / 3) + '" height="' + h + '" fill="' + color + '" opacity="' + o + '"/><text x="' + (x + w / 6) + '" y="' + (h / 2 + 6) + '" fill="#fff" font-size="20" font-weight="800" text-anchor="middle">' + p + '%</text><text x="' + (x + w / 6) + '" y="' + (h - 8) + '" fill="#fff" opacity=".7" font-size="9" text-anchor="middle">' + lab + "</text>"; }
    return '<svg class="pitch" viewBox="0 0 ' + w + " " + h + '" role="img" aria-label="Attack zones">' + col(0, L_, "LEFT") + col(w / 3, C, "CENTER") + col(2 * w / 3, R, "RIGHT") +
      '<rect x="1" y="1" width="' + (w - 2) + '" height="' + (h - 2) + '" fill="none" stroke="#fff" opacity=".5"/><rect x="60" y="1" width="80" height="26" fill="none" stroke="#fff" opacity=".5"/><path d="M80 130h40" stroke="#fff"/></svg>' +
      '<div class="small" style="text-align:center">Attacking up the page. Left and right as the team attacks.</div>';
  }
  function shotMap(shots, homeName, awayName) {
    if (!shots || !shots.length) return "";
    var dots = shots.map(function (s) {
      if (s.x == null || s.y == null) return "";
      var x = s.x > 1.5 ? s.x / 105 : s.x, y = s.y > 1.5 ? s.y / 68 : s.y, r = 3 + (s.xg || 0.05) * 14;
      return '<circle cx="' + (x * 200).toFixed(1) + '" cy="' + (y * 130).toFixed(1) + '" r="' + r.toFixed(1) + '" fill="' + (s.team === "home" ? "#c4123f" : "#9aa6b8") + '" opacity=".8"/>';
    }).join("");
    return '<h2>Shot map</h2><svg class="pitch" viewBox="0 0 200 130"><rect x="1" y="1" width="198" height="128" fill="#0f2a1c" stroke="#fff" opacity=".9"/><path d="M100 1v128" stroke="#fff" opacity=".4"/>' + dots + '</svg><div class="small" style="text-align:center">Dot size is xG. Source field coordinates may differ, treat as a rough map.</div>';
  }

  /* ---------- team synopsis ---------- */
  var SECTIONS = [
    ["Build-up style", ["poss", "passes", "pass_pct", "long_pct"]],
    ["Chance creation", ["shots", "sot", "xg", "crosses", "cross_pct", "corners", "conv", "goals"]],
    ["Pressing and defending", ["ppda", "tackles", "interceptions", "fouls"]],
    ["Vulnerabilities (what they concede)", ["shots_ag", "sot_ag", "xg_ag", "crosses_ag", "corners_ag", "goals_ag"]]
  ];
  var LBL = { poss: "Possession %", passes: "Passes", pass_pct: "Pass accuracy %", long_pct: "Long ball share %", shots: "Shots", sot: "Shots on target", xg: "xG", crosses: "Crosses", cross_pct: "Cross accuracy %", corners: "Corners", conv: "Shot conversion %", goals: "Goals", ppda: "PPDA (approx, low = high press)", tackles: "Tackles", interceptions: "Interceptions", fouls: "Fouls", shots_ag: "Shots conceded", sot_ag: "Shots on target conceded", xg_ag: "xG conceded", crosses_ag: "Crosses conceded", corners_ag: "Corners conceded", goals_ag: "Goals conceded" };
  var TERM = { poss: "possession", passes: "passes", pass_pct: "pass_accuracy", long_pct: "long_ball_share", shots: "shots", sot: "sot", xg: "xg", crosses: "crosses", cross_pct: "cross_accuracy", corners: "corners", conv: "conversion", goals: "goals", ppda: "ppda", tackles: "tackles", interceptions: "interceptions", fouls: "fouls", shots_ag: "shots", sot_ag: "sot", xg_ag: "xg", crosses_ag: "crosses", corners_ag: "corners", goals_ag: "goals" };
  var DEC = { poss: 1, passes: 0, pass_pct: 1, long_pct: 1, shots: 1, sot: 1, xg: 2, crosses: 1, cross_pct: 1, corners: 1, conv: 1, goals: 2, ppda: 1, tackles: 1, interceptions: 1, fouls: 1, shots_ag: 1, sot_ag: 1, xg_ag: 2, crosses_ag: 1, corners_ag: 1, goals_ag: 2 };

  function teamView(block, isOpp) {
    if (!block || !S.prof) return '<div class="empty">No profile data yet. The weekly job builds it automatically.</div>';
    var t = S.prof.teams[block.profile_key]; if (!t) return '<div class="empty">Team not found in season profiles.</div>';
    var color = isOpp ? "#9aa6b8" : "#c4123f";
    var h = '<h2>' + esc(block.name) + " this season (" + t.games + " games)</h2>";
    h += '<div class="sec form" style="padding:12px 14px"><b>Last 5:</b> ' + t.form.last5.results.map(function (r) { return "<span class=\"" + r + "\">" + r + "</span>"; }).join("") +
      '<div class="small" style="margin-top:6px">' + fmt(t.form.last5.ppg, 1) + " pts per game vs " + fmt(t.form.season.ppg, 1) + " on the season. Goal diff last 5: " + fmt(t.form.last5.gf - t.form.last5.ga, 1) + " per game.</div></div>";
    var asv = pitch(block.attack_side || t.attack_side, color);
    if (asv) h += "<h2>Attack zones</h2>" + asv;
    h += "<h2>What they are trying to do</h2>" + cards(block.cards, isOpp, 8);
    SECTIONS.forEach(function (sec) {
      var rows = sec[1].filter(function (k) { return t.metrics[k]; }).map(function (k) {
        var m = t.metrics[k];
        return '<div class="metric" style="--accent:' + color + '"><div class="lbl">' + L(TERM[k], LBL[k]) + '</div><div class="val">' + fmt(m.v, DEC[k]) + '</div><div class="bar"><i style="width:' + Math.max(m.pct, 3) + '%"></i></div><div class="rk">#' + m.rank + " of " + m.of + " in MLS</div></div>";
      }).join("");
      if (rows) h += "<h2>" + sec[0] + '</h2><div class="sec">' + rows + "</div>";
    });
    var gaps = [];
    if (!(block.attack_side || t.attack_side)) gaps.push("attack zones (left, center, right)");
    if (!t.metrics.xg) gaps.push("xG");
    gaps.push("key player g+ (not in the free feeds yet)");
    h += '<p class="small">Not available from the free sources right now: ' + esc(gaps.join(", ")) + ". Sections hide when their data is missing.</p>";
    return h;
  }

  /* ---------- matchup ---------- */
  function matchupView() {
    var mu = S.mu; if (!mu) return '<div class="empty">No matchup yet. It builds automatically before each RSL kickoff.</div>';
    var h = '<h2>Likely game script</h2><div class="script">' + esc(mu.matchup.script || "Not enough data for a script.") + "</div>";
    h += "<h2>Keys to the game</h2>" + (mu.matchup.keys.length ? cards(mu.matchup.keys, undefined, 5) : '<div class="empty">No strong strength-versus-weakness overlap found in the season data. That itself says this looks like an even matchup.</div>');
    h += '<h2>Side by side (per game, rank in MLS)</h2><div class="sec" style="padding:4px 12px"><div class="cmp small"><div class="a"><b style="color:#fff">RSL</b></div><div class="mid">stat</div><div class="b"><b style="color:var(--opp)">' + esc(mu.opp.name) + "</b></div></div>";
    mu.compare.forEach(function (r) {
      var ra = +r.rsl_rank.split("/")[0], rb = +r.opp_rank.split("/")[0], N = +r.rsl_rank.split("/")[1];
      h += '<div class="cmp"><div class="a"><div class="n">' + fmt(r.rsl, r.key === "xg" || r.key === "xg_ag" || r.key.indexOf("goals") === 0 ? 2 : 1) + '</div><div class="r">#' + ra + '</div><div class="mini"><i style="width:' + (100 - (ra - 1) / (N - 1) * 100) + '%"></i></div></div><div class="mid">' + L(r.term, r.label) + '</div><div class="b"><div class="n">' + fmt(r.opp, r.key === "xg" || r.key === "xg_ag" || r.key.indexOf("goals") === 0 ? 2 : 1) + '</div><div class="r">#' + rb + '</div><div class="mini"><i style="width:' + (100 - (rb - 1) / (N - 1) * 100) + '%"></i></div></div></div>';
    });
    h += '</div><button class="btn" onclick="__copy(\'pre\')">Copy for Claude</button><p class="small">Copies the matchup and numbers as a prompt you can paste into your Claude app for follow-up questions.</p>';
    return h;
  }

  /* ---------- halftime ---------- */
  function htView() {
    var ht = S.ht, mu = S.mu;
    var cur = S.live && S.live.match ? S.live.match.id : null;
    if (!ht || (mu && ht.match_id && mu.match && ht.match_id !== mu.match.id && !DEMO)) {
      var st = S.live && S.live.snapshot ? S.live.snapshot : null;
      return '<div class="empty"><b>Halftime report fills itself in at the break.</b><br>' + (st ? "Match status: " + esc(st.status) + (st.minute ? ", minute " + esc(st.minute) : "") + "." : "No match in progress.") + '<br>Check back at halftime. This page refreshes on its own.</div>';
    }
    var teams = ht.teams, h = "";
    h += '<div class="chips"><span class="chip"><b>' + esc(teams.home) + " " + ht.score.home + " - " + ht.score.away + " " + esc(teams.away) + '</b></span><span class="chip">Data: <b>' + esc(ht.source) + (ht.source_role ? " (" + esc(ht.source_role) + ")" : "") + "</b></span></div>";
    if (ht.note) h += '<div class="banner">' + esc(ht.note) + "</div>";
    var rslSide = ht.rsl_side || "home";
    var adv = ht.cards.filter(function (c) { return c.scope === "adjustment"; });
    var work = ht.cards.filter(function (c) { return c.scope === "effectiveness" && c.id.indexOf("xg_good") > -1; });
    var nowork = ht.cards.filter(function (c) { return c.scope === "effectiveness" && c.id.indexOf("xg_good") < 0; });
    var dev = ht.cards.filter(function (c) { return c.scope === "deviation"; });
    h += "<h2>What is working</h2>" + (work.length ? cards(work) : '<div class="empty">Nothing stands out as clearly working yet.</div>');
    h += "<h2>What is not working</h2>" + (nowork.length ? cards(nowork) : '<div class="empty">No clear failing pattern in the first half numbers.</div>');
    h += "<h2>Expected second half adjustments</h2>" + (adv.length ? cards(adv) : '<div class="empty">No strong adjustment signal.</div>');
    h += "<h2>Doing something different from their season</h2>" + (dev.length ? cards(dev, undefined, 5) : '<div class="empty">Both teams are close to their season norms.</div>');
    h += "<h2>Plan versus reality</h2>";
    ["home", "away"].forEach(function (s) {
      var rows = ht.table.filter(function (r) { return r.side === s; });
      if (!rows.length) return;
      h += '<div class="sec"><table><tr><th>' + esc(teams[s]) + '</th><th class="n">Season half</th><th class="n">First half</th><th class="n">Diff</th></tr>' + rows.map(function (r) {
        var d = r.dev_pct, cls = d == null ? "" : (d >= 15 ? "up" : d <= -15 ? "down" : "");
        return "<tr><td>" + L(TERM[r.key] || "", r.label.replace(" (per half)", "")) + '</td><td class="n">' + fmt(r.norm, 1) + '</td><td class="n">' + fmt(r.actual, 1) + '</td><td class="n dev ' + cls + '">' + (d == null ? "" : (d > 0 ? "+" : "") + d + "%") + "</td></tr>";
      }).join("") + "</table></div>";
    });
    var pa = ht.attack_side && ht.attack_side.home && ht.attack_side.home.left_pct != null;
    if (pa) h += '<h2>First half attack zones</h2><div class="pitches"><figure>' + pitch(ht.attack_side.home, rslSide === "home" ? "#c4123f" : "#9aa6b8") + "<figcaption>" + esc(teams.home) + "</figcaption></figure><figure>" + pitch(ht.attack_side.away, rslSide === "away" ? "#c4123f" : "#9aa6b8") + "<figcaption>" + esc(teams.away) + "</figcaption></figure></div>";
    if (ht.has_shot_map) h += shotMap(ht.shots);
    var miss = []; if (!ht.has_xg) miss.push("xG"); if (!ht.has_shot_map) miss.push("shot map"); if (!pa) miss.push("attack zones");
    if (miss.length) h += '<p class="small">Hidden because this source does not provide them: ' + esc(miss.join(", ")) + ".</p>";
    h += '<p class="small"><b>Measured</b> means the card follows from the numbers shown. <b>Inference</b> means it is a reasoned prediction.</p><button class="btn" onclick="__copy(\'ht\')">Copy for Claude</button>';
    return h;
  }

  /* ---------- learn ---------- */
  function learnView() {
    var keys = Object.keys(G);
    var h = '<h2>Learn mode</h2><p class="small">Tap any stat name in the app for a plain-English definition. Every insight card follows the same chain: Data, Meaning, Watch for.</p><input class="search" id="q" placeholder="Search terms (xG, PPDA, crosses)" autocomplete="off"><div id="gl"></div>';
    setTimeout(function () {
      function draw(q) {
        q = (q || "").toLowerCase();
        $("gl").innerHTML = keys.filter(function (k) { return !q || (G[k].name + G[k].short + G[k].why).toLowerCase().indexOf(q) > -1; }).map(function (k) {
          return '<div class="card" onclick="__learn(\'' + k + '\')"><h3>' + esc(G[k].name) + '</h3><div class="v">' + esc(G[k].short) + "</div></div>";
        }).join("") || '<div class="empty">No match.</div>';
      }
      draw(""); var q = $("q"); if (q) q.oninput = function () { draw(q.value); };
    }, 0);
    return h;
  }

  /* ---------- copy for Claude ---------- */
  function cardText(c) { return "- [" + c.confidence + "] " + c.title + "\n  Data: " + c.data + "\n  Meaning: " + c.meaning + "\n  Watch for: " + c.watch; }
  function buildPrompt(kind) {
    var mu = S.mu, ht = S.ht, snap = S.live && S.live.snapshot, L_ = [];
    L_.push("I am watching Real Salt Lake. Use the data below to explain what each team is trying to do tactically. Answer every point in this format: Data (the numbers), Meaning (what it says the team is doing), Watch for (what I will see on the field). Keep it direct and brief, and do not use em dashes. Mark anything that is a guess as Inference.");
    if (mu) {
      L_.push("\nMATCH: " + mu.match.home + " vs " + mu.match.away + " (" + new Date(mu.match.date).toLocaleString() + ")");
      if (kind === "ht" && ht) L_.push("SCORE: " + ht.teams.home + " " + ht.score.home + " - " + ht.score.away + " " + ht.teams.away + " at halftime (minute " + (ht.minute || 45) + ")");
      else if (snap && snap.status !== "pre") L_.push("SCORE: " + snap.teams.home.name + " " + snap.teams.home.score + " - " + snap.teams.away.score + " " + snap.teams.away.name + ", minute " + (snap.minute || "?"));
      L_.push("\nSEASON BASELINES (per game, rank in MLS, 1 = highest):");
      mu.compare.forEach(function (r) { L_.push("- " + r.label + ": RSL " + r.rsl + " (#" + r.rsl_rank.split("/")[0] + "), " + mu.opp.name + " " + r.opp + " (#" + r.opp_rank.split("/")[0] + ")"); });
      L_.push("\nGENERATED KEYS TO THE GAME:"); mu.matchup.keys.forEach(function (c) { L_.push(cardText(c)); });
      L_.push("\nGAME SCRIPT: " + mu.matchup.script);
    }
    if (kind === "ht" && ht) {
      L_.push("\nFIRST HALF VS SEASON NORMS (season half = per game divided by 2):");
      ht.table.forEach(function (r) { L_.push("- " + r.team + " " + r.label + ": first half " + r.actual + " vs norm " + r.norm + (r.dev_pct == null ? "" : " (" + (r.dev_pct > 0 ? "+" : "") + r.dev_pct + "%)")); });
      L_.push("\nGENERATED HALFTIME INSIGHTS:"); ht.cards.forEach(function (c) { L_.push(cardText(c)); });
      L_.push("\nData source: " + ht.source + ". Missing from this source: " + [!ht.has_xg && "xG", !ht.has_shot_map && "shot map"].filter(Boolean).join(", "));
    }
    L_.push("\nMy question: what is the most important thing to watch for " + (kind === "ht" ? "in the second half" : "in this game") + ", and what should I expect each coach to change?");
    return L_.join("\n");
  }
  window.__copy = function (kind) {
    var txt = buildPrompt(kind);
    function ok() { openSheet("<h3>Copied</h3><p>The prompt is on your clipboard. Paste it into your Claude app.</p>"); }
    function fallback() { var ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); ok(); } catch (e) { openSheet("<h3>Copy manually</h3><textarea style='width:100%;height:240px'>" + esc(txt) + "</textarea>"); } document.body.removeChild(ta); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(ok, fallback); else fallback();
  };

  /* ---------- header, banners, tabs ---------- */
  function header() {
    var mu = S.mu;
    if (mu) {
      var m = mu.match, rslHome = m.rsl_is_home;
      $("teams").innerHTML = rslHome ? '<span class="rsl">RSL</span> v <span class="opp">' + esc(mu.opp.name) + "</span>" : '<span class="opp">' + esc(mu.opp.name) + '</span> v <span class="rsl">RSL</span>';
      $("when").textContent = new Date(m.date).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
    } else $("teams").textContent = "RSL Tactics";
    var chips = [], hl = S.health && S.health.sources || {};
    var snap = S.live && S.live.snapshot;
    if (snap && snap.source) chips.push('<span class="chip">Live data: <b>' + esc(snap.source) + (snap.source_role ? " (" + esc(snap.source_role) + ")" : "") + "</b> &middot; " + ago(snap.fetched_at) + "</span>");
    if (S.prof) chips.push('<span class="chip">Season data: <b>' + esc(S.prof.source) + "</b> &middot; " + ago(S.prof.generated_at) + "</span>");
    Object.keys(hl).forEach(function (k) { var s = hl[k]; if (s.ok === null) return; chips.push('<span class="chip"><i class="dot ' + (s.ok ? "ok" : "bad") + '"></i>' + esc(k) + "</span>"); });
    $("chips").innerHTML = chips.join("");
    var b = "";
    if (DEMO) b += '<div class="banner demo"><b>DEMO DATA.</b> Synthetic teams and numbers to preview the app. Not real.</div>';
    if (mu && mu.match.stage === "playoff") b += '<div class="banner" style="background:#101e2e;border-color:#25507f;color:#a9cdf5"><b>Playoff match.</b> Season numbers are regular season. Expect a tighter game, and extra time or penalties are possible.</div>';
    if (mu && mu.mode === "replay") b += '<div class="banner">Replay mode: no upcoming RSL match found, so this shows the most recent completed match.</div>';
    $("banners").innerHTML = b;
    var live = snap && (snap.status === "live" || snap.status === "ht");
    $("htbtn").innerHTML = $("htbtn").innerHTML.replace(/<span class="pip"><\/span>/, "") + (S.ht ? '<span class="pip"></span>' : "");
  }
  function render() {
    header();
    $("t-rsl").innerHTML = teamView(S.mu && S.mu.rsl, false);
    $("t-opp").innerHTML = teamView(S.mu && S.mu.opp, true);
    $("t-match").innerHTML = matchupView();
    $("t-ht").innerHTML = htView();
    if (!$("t-learn").innerHTML) $("t-learn").innerHTML = learnView();
  }
  function show(tab) {
    document.querySelectorAll(".tab").forEach(function (e) { e.classList.toggle("on", e.id === "t-" + tab); });
    document.querySelectorAll("nav button").forEach(function (e) { e.classList.toggle("on", e.dataset.tab === tab); });
    try { history.replaceState(null, "", "#" + tab); } catch (e) {}
    window.scrollTo(0, 0);
  }
  document.querySelectorAll("nav button").forEach(function (b) { b.onclick = function () { show(b.dataset.tab); }; });

  function load(first) {
    return Promise.all([getJSON("profiles.json"), getJSON("matchup.json"), getJSON("halftime.json"), getJSON("live.json"), getJSON("health.json"), getJSON("schedule.json")]).then(function (r) {
      S.prof = r[0] || S.prof; S.mu = r[1] || S.mu; S.ht = r[2]; S.live = r[3]; S.health = r[4]; S.sched = r[5];
      render();
      if (first) { var h = (location.hash || "").slice(1); if (h && document.getElementById("t-" + h)) show(h); else if (S.ht && S.live && S.live.snapshot && S.live.snapshot.status === "ht") show("ht"); }
    });
  }
  load(true);
  setInterval(function () { if (!document.hidden) { var s = S.live && S.live.snapshot; if (s && (s.status === "live" || s.status === "ht")) load(false); } }, 60000);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) load(false); });
  if ("serviceWorker" in navigator && !DEMO) navigator.serviceWorker.register("sw.js").catch(function () {});
})();
