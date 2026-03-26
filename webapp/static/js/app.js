/* ===================================================
   Shalva Web App — Main Application JS
   =================================================== */

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function esc(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

// ---------------------------------------------------------------------------
// API Helper
// ---------------------------------------------------------------------------
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Session Init
// ---------------------------------------------------------------------------
async function initSession() {
  await api("/api/session", { method: "POST", body: { name: "אורח" } });
  loadHomeStats();
}

// ---------------------------------------------------------------------------
// Navigation & Screens
// ---------------------------------------------------------------------------
let currentScreen = "screen-home";

function showScreen(id) {
  document.querySelectorAll(".screen").forEach((s) => {
    s.classList.remove("active");
    s.style.display = "";
  });
  const el = document.getElementById(id);
  if (el) {
    el.classList.add("active");
    // Chat screens need flex display
    if (id === "screen-chat" || id === "screen-navigator") {
      el.style.display = "flex";
    }
  }
  currentScreen = id;

  // Scroll to top
  document.getElementById("appContent").scrollTop = 0;

  // Update nav active state
  document.querySelectorAll(".nav-item").forEach((n) => {
    n.classList.toggle("active", n.dataset.screen === id);
  });

  // Load data for specific screens
  if (id === "screen-analytics") loadAnalytics();
  if (id === "screen-home") loadHomeStats();
}

function navTo(id) {
  showScreen(id);
}

// ---------------------------------------------------------------------------
// Home Stats
// ---------------------------------------------------------------------------
async function loadHomeStats() {
  try {
    const data = await api("/api/analytics");
    if (data.has_data) {
      document.getElementById("statAvg").textContent = data.avg_anxiety;
      document.getElementById("statTotal").textContent = data.total_reports;
    }
  } catch (e) {
    /* silent */
  }
}

// ---------------------------------------------------------------------------
// Quick Report
// ---------------------------------------------------------------------------
let qrData = {};

function initQuickReport() {
  const grid = document.getElementById("qrAnxietyGrid");
  grid.innerHTML = "";
  for (let i = 1; i <= 10; i++) {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.textContent = i;
    btn.onclick = () => selectQrAnxiety(i, btn);
    grid.appendChild(btn);
  }
}

function qrNextStep() {
  const desc = document.getElementById("qrDescription").value.trim();
  if (!desc) return;
  qrData.description = desc;

  document.getElementById("qrStep1").style.display = "none";
  document.getElementById("qrStep2").style.display = "block";

  // Update step indicator
  const bars = document.querySelectorAll("#qrSteps .step-bar");
  bars[0].classList.remove("active");
  bars[0].classList.add("done");
  bars[1].classList.add("active");
}

async function selectQrAnxiety(level, btn) {
  document.querySelectorAll("#qrAnxietyGrid .option-btn").forEach((b) => b.classList.remove("selected"));
  btn.classList.add("selected");
  qrData.anxiety_level = level;

  // Submit
  const result = await api("/api/reports/quick", { method: "POST", body: qrData });

  document.getElementById("qrStep2").style.display = "none";
  document.getElementById("qrResult").style.display = "block";

  const bars = document.querySelectorAll("#qrSteps .step-bar");
  bars[1].classList.remove("active");
  bars[1].classList.add("done");

  document.getElementById("qrResultMsg").textContent =
    `✅ נשמר! רמת חרדה: ${level}/10\n${result.recommendation || ""}`;
}

function resetQuickReport() {
  qrData = {};
  document.getElementById("qrDescription").value = "";
  document.getElementById("qrStep1").style.display = "block";
  document.getElementById("qrStep2").style.display = "none";
  document.getElementById("qrResult").style.display = "none";
  const bars = document.querySelectorAll("#qrSteps .step-bar");
  bars.forEach((b) => { b.classList.remove("active", "done"); });
  bars[0].classList.add("active");
  document.querySelectorAll("#qrAnxietyGrid .option-btn").forEach((b) => b.classList.remove("selected"));
}

// ---------------------------------------------------------------------------
// Full Report
// ---------------------------------------------------------------------------
let frData = {};
let frCurrentStep = 1;
let reportOptions = {};

async function initFullReport() {
  // Load options
  if (!reportOptions.locations) {
    reportOptions = await api("/api/reports/options");
  }

  // Anxiety grid
  const grid = document.getElementById("frAnxietyGrid");
  grid.innerHTML = "";
  for (let i = 1; i <= 10; i++) {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.textContent = i;
    btn.onclick = () => selectFrOption("anxiety_level", i, btn, "frAnxietyGrid", 3);
    grid.appendChild(btn);
  }

  // Location grid
  const locGrid = document.getElementById("frLocationGrid");
  locGrid.innerHTML = "";
  (reportOptions.locations || []).forEach((loc) => {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.textContent = loc;
    btn.onclick = () => selectFrOption("location", loc, btn, "frLocationGrid", 4);
    locGrid.appendChild(btn);
  });

  // People grid
  const pGrid = document.getElementById("frPeopleGrid");
  pGrid.innerHTML = "";
  (reportOptions.people || []).forEach((p) => {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.textContent = p;
    btn.onclick = () => selectFrOption("people_around", p, btn, "frPeopleGrid", 5);
    pGrid.appendChild(btn);
  });

  // Weather grid
  const wGrid = document.getElementById("frWeatherGrid");
  wGrid.innerHTML = "";
  (reportOptions.weather || []).forEach((w) => {
    const btn = document.createElement("button");
    btn.className = "option-btn";
    btn.textContent = w;
    btn.onclick = () => selectFrOption("weather", w, btn, "frWeatherGrid", -1);
    wGrid.appendChild(btn);
  });
}

function frNext(step) {
  if (step === 2) {
    const desc = document.getElementById("frDescription").value.trim();
    if (!desc) return;
    frData.description = desc;
  }

  frCurrentStep = step;
  for (let i = 1; i <= 5; i++) {
    document.getElementById(`frStep${i}`).style.display = i === step ? "block" : "none";
  }

  // Update step indicator
  const bars = document.querySelectorAll("#frSteps .step-bar");
  bars.forEach((b, idx) => {
    b.classList.remove("active", "done");
    if (idx < step - 1) b.classList.add("done");
    else if (idx === step - 1) b.classList.add("active");
  });
}

async function selectFrOption(field, value, btn, gridId, nextStep) {
  document.querySelectorAll(`#${gridId} .option-btn`).forEach((b) => b.classList.remove("selected"));
  btn.classList.add("selected");
  frData[field] = value;

  if (nextStep > 0) {
    setTimeout(() => frNext(nextStep), 200);
  } else {
    // Last step - submit
    const result = await api("/api/reports/full", { method: "POST", body: frData });

    for (let i = 1; i <= 5; i++) document.getElementById(`frStep${i}`).style.display = "none";
    document.getElementById("frResult").style.display = "block";

    const bars = document.querySelectorAll("#frSteps .step-bar");
    bars.forEach((b) => { b.classList.remove("active"); b.classList.add("done"); });

    document.getElementById("frResultMsg").textContent =
      `🎉 דיווח מלא נשמר!\nרמת חרדה: ${frData.anxiety_level}/10\n${result.recommendation || ""}`;
  }
}

function resetFullReport() {
  frData = {};
  frCurrentStep = 1;
  document.getElementById("frDescription").value = "";
  for (let i = 1; i <= 5; i++) {
    document.getElementById(`frStep${i}`).style.display = i === 1 ? "block" : "none";
  }
  document.getElementById("frResult").style.display = "none";
  const bars = document.querySelectorAll("#frSteps .step-bar");
  bars.forEach((b) => { b.classList.remove("active", "done"); });
  bars[0].classList.add("active");
  document.querySelectorAll("#screen-full-report .option-btn").forEach((b) => b.classList.remove("selected"));
}

// ---------------------------------------------------------------------------
// Venting
// ---------------------------------------------------------------------------
let ventingContent = "";

function submitVenting() {
  const content = document.getElementById("ventingContent").value.trim();
  if (!content) return;
  ventingContent = content;
  document.getElementById("ventingForm").style.display = "none";
  document.getElementById("ventingSaveChoice").style.display = "block";
}

async function saveVenting(save) {
  await api("/api/venting", { method: "POST", body: { content: ventingContent, save_for_analysis: save } });
  document.getElementById("ventingSaveChoice").style.display = "none";
  document.getElementById("ventingDone").style.display = "block";
  document.getElementById("ventingDoneMsg").textContent = save
    ? "✅ נשמר לניתוח! הפריקה תעזור לי להבין דפוסים."
    : "✅ הפריקה הושלמה! מקווה שזה עזר. 🌟";
}

function resetVenting() {
  ventingContent = "";
  document.getElementById("ventingContent").value = "";
  document.getElementById("ventingForm").style.display = "block";
  document.getElementById("ventingSaveChoice").style.display = "none";
  document.getElementById("ventingDone").style.display = "none";
}

// ---------------------------------------------------------------------------
// AI Chat
// ---------------------------------------------------------------------------
async function startChat() {
  showScreen("screen-chat");
  document.getElementById("chatMessages").innerHTML = "";

  const result = await api("/api/chat/start", { method: "POST" });
  if (result.message) {
    addChatBubble(result.message, "bot");
  }
}

function addChatBubble(text, type) {
  const el = document.createElement("div");
  el.className = `chat-bubble ${type}`;
  el.textContent = text;
  document.getElementById("chatMessages").appendChild(el);
  document.getElementById("chatMessages").scrollTop = 999999;
}

async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";

  addChatBubble(msg, "user");
  document.getElementById("chatTyping").classList.add("active");

  try {
    const result = await api("/api/chat/message", { method: "POST", body: { message: msg } });
    document.getElementById("chatTyping").classList.remove("active");
    if (result.crisis) {
      const el = document.createElement("div");
      el.className = "crisis-alert";
      el.textContent = result.message;
      document.getElementById("chatMessages").appendChild(el);
    } else if (result.message) addChatBubble(result.message, "bot");
    else if (result.error) addChatBubble("מצטער, קרתה שגיאה. נסה שוב.", "bot");
  } catch (e) {
    document.getElementById("chatTyping").classList.remove("active");
    addChatBubble("שגיאת תקשורת. נסה שוב.", "bot");
  }
}

async function endChat() {
  await api("/api/chat/end", { method: "POST" });
  showScreen("screen-home");
}

// ---------------------------------------------------------------------------
// Mental Health Navigator
// ---------------------------------------------------------------------------
const navTopicQuestions = {
  hotlines: "מה קווי החירום והתמיכה הרגשית הזמינים בישראל?",
  kupat: "איך מתחילים טיפול נפשי דרך קופת החולים?",
  types: "מה סוגי הטיפולים הנפשיים שזמינים בישראל?",
  costs: "כמה עולה טיפול נפשי בישראל?",
  workplace: "מה הזכויות שלי בנושא בריאות הנפש בעבודה?",
  ptsd: "מה המשאבים לטיפול ב-PTSD וטראומה בישראל?",
};

async function startNavigator() {
  showScreen("screen-navigator");
  document.getElementById("navMessages").innerHTML = "";

  const result = await api("/api/navigator/start", { method: "POST" });
  if (result.message) addNavBubble(result.message, "bot");
}

function addNavBubble(text, type) {
  const el = document.createElement("div");
  el.className = `chat-bubble ${type}`;
  el.textContent = text;
  document.getElementById("navMessages").appendChild(el);
  document.getElementById("navMessages").scrollTop = 999999;
}

async function sendNavTopic(topic) {
  const question = navTopicQuestions[topic];
  if (!question) return;
  addNavBubble(question, "user");
  document.getElementById("navTyping").classList.add("active");

  try {
    const result = await api("/api/navigator/message", { method: "POST", body: { message: question } });
    document.getElementById("navTyping").classList.remove("active");
    if (result.crisis) {
      const el = document.createElement("div");
      el.className = "crisis-alert";
      el.textContent = result.message;
      document.getElementById("navMessages").appendChild(el);
    } else if (result.message) {
      addNavBubble(result.message, "bot");
    } else if (result.error) {
      addNavBubble("מצטער, קרתה שגיאה. נסה שוב.", "bot");
    }
  } catch (e) {
    document.getElementById("navTyping").classList.remove("active");
    addNavBubble("שגיאת תקשורת. נסה שוב.", "bot");
  }
}

async function sendNavMessage() {
  const input = document.getElementById("navInput");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";

  addNavBubble(msg, "user");
  document.getElementById("navTyping").classList.add("active");

  try {
    const result = await api("/api/navigator/message", { method: "POST", body: { message: msg } });
    document.getElementById("navTyping").classList.remove("active");
    if (result.crisis) {
      const el = document.createElement("div");
      el.className = "crisis-alert";
      el.textContent = result.message;
      document.getElementById("navMessages").appendChild(el);
    } else if (result.message) {
      addNavBubble(result.message, "bot");
    } else if (result.error) {
      addNavBubble("מצטער, קרתה שגיאה. נסה שוב.", "bot");
    }
  } catch (e) {
    document.getElementById("navTyping").classList.remove("active");
    addNavBubble("שגיאת תקשורת. נסה שוב.", "bot");
  }
}

async function endNavigator() {
  await api("/api/navigator/end", { method: "POST" });
  showScreen("screen-more");
}

// ---------------------------------------------------------------------------
// Panic Mode — Breathing Exercise
// ---------------------------------------------------------------------------
let breathingTimer = null;
let breathingCycle = 0;

function startBreathing() {
  const btn = document.getElementById("breathBtn");
  btn.textContent = "⏹️ הפסק";
  btn.onclick = stopBreathing;
  breathingCycle = 0;
  runBreathCycle();
}

function runBreathCycle() {
  if (breathingCycle >= 3) {
    stopBreathing();
    document.getElementById("breathText").textContent = "כל הכבוד! 🎉";
    return;
  }

  const circle = document.getElementById("breathCircle");
  const text = document.getElementById("breathText");

  // Inhale
  circle.className = "breathing-circle inhale";
  text.textContent = "שאיפה...";
  breathingTimer = setTimeout(() => {
    // Hold
    circle.className = "breathing-circle hold";
    text.textContent = "החזק...";
    breathingTimer = setTimeout(() => {
      // Exhale
      circle.className = "breathing-circle exhale";
      text.textContent = "נשיפה...";
      breathingTimer = setTimeout(() => {
        breathingCycle++;
        text.textContent = `מחזור ${breathingCycle}/3`;
        runBreathCycle();
      }, 6000);
    }, 4000);
  }, 4000);
}

function stopBreathing() {
  if (breathingTimer) clearTimeout(breathingTimer);
  breathingTimer = null;

  const circle = document.getElementById("breathCircle");
  const text = document.getElementById("breathText");
  const btn = document.getElementById("breathBtn");

  circle.className = "breathing-circle";
  text.textContent = "מוכן?";
  btn.textContent = "ננשום יחד 4-4-6";
  btn.onclick = startBreathing;
}

// ---------------------------------------------------------------------------
// Panic Mode — Techniques
// ---------------------------------------------------------------------------
let guidedTimer = null;

function startTechnique(type) {
  if (type === "bodyscan") {
    startBodyScan();
  } else if (type === "pmr") {
    startPMR();
  } else {
    const msgs = {
      water: "💧 לך לשטוף פנים במים קרים. כשתחזור, לחץ על 'סיימתי'.",
      count: "🔢 נתחיל: 100… 93… 86… 79… 72… 65… 58… 51… 44… 37… 30… 23… 16… 9… 2. כל הכבוד!",
      press: "🤚 לחץ על הנקודה בין האגודל לאצבע למשך 30 שניות.",
      move: "🚶 קום וזוז דקה-שתיים. הליכה, מתיחות, כל תנועה.",
    };
    document.getElementById("panicMain").style.display = "none";
    document.getElementById("panicGuided").style.display = "block";
    document.getElementById("guidedTitle").innerHTML = `<div style="font-size:1.5rem;margin-bottom:0.5rem;">${type === "water" ? "💧" : type === "count" ? "🔢" : type === "press" ? "🤚" : "🚶"}</div>`;
    document.getElementById("guidedSteps").innerHTML = `<div class="card text-center">${msgs[type]}</div>`;
  }
}

function startBodyScan() {
  const steps = [
    ["🦶 כפות הרגליים", "הפנה את תשומת הלב לכפות הרגליים. מה אתה מרגיש? פשוט שים לב."],
    ["🦵 השוקיים והברכיים", "עלה לאט לשוקיים. שחרר כל מתח."],
    ["🦿 הירכיים והאגן", "המשך לירכיים. נשום עמוק ושחרר."],
    ["🫁 הבטן והחזה", "הרגש את הבטן עולה ויורדת. שחרר מתח."],
    ["💪 הכתפיים והזרועות", "הורד כתפיים מהאוזניים. שחרר."],
    ["🧠 הצוואר והראש", "שחרר לסת, הרפה מצח. הרגש רוגע."],
  ];

  document.getElementById("panicMain").style.display = "none";
  document.getElementById("panicGuided").style.display = "block";
  document.getElementById("guidedTitle").innerHTML = '<div style="font-size:1.5rem;">🧘</div><div style="font-weight:600;">סריקת גוף</div>';

  let step = 0;
  const container = document.getElementById("guidedSteps");

  function showStep() {
    if (step >= steps.length) {
      container.innerHTML = '<div class="card text-center alert-success">✨ סיימנו! הגוף קל ומשוחרר.</div>';
      return;
    }
    container.innerHTML = `<div class="card"><div style="font-weight:600;margin-bottom:0.35rem;">שלב ${step + 1}/${steps.length}: ${steps[step][0]}</div><div class="text-secondary text-sm">${steps[step][1]}</div></div>`;
    step++;
    guidedTimer = setTimeout(showStep, 12000);
  }
  showStep();
}

function startPMR() {
  const groups = [
    ["✊ כפות הידיים", "כווץ אגרופים חזקים…", "שחרר… הרגש את ההבדל."],
    ["💪 הזרועות", "כווץ שרירי הזרועות…", "שחרר… תן לזרועות ליפול."],
    ["🫁 הכתפיים", "הרם כתפיים לאוזניים…", "הורד ושחרר…"],
    ["😤 הפנים", "כווץ כל שרירי הפנים…", "שחרר… הרפה מצח, עיניים, לסת."],
    ["🫃 הבטן", "כווץ שרירי הבטן…", "שחרר…"],
    ["🦵 הרגליים", "כווץ ירכיים, שוקיים, כפות רגליים…", "שחרר… הרגש כבדות ורוגע."],
  ];

  document.getElementById("panicMain").style.display = "none";
  document.getElementById("panicGuided").style.display = "block";
  document.getElementById("guidedTitle").innerHTML = '<div style="font-size:1.5rem;">💪</div><div style="font-weight:600;">הרפיית שרירים (PMR)</div>';

  let step = 0;
  let phase = "tense"; // "tense" then "release"
  const container = document.getElementById("guidedSteps");

  function showStep() {
    if (step >= groups.length) {
      container.innerHTML = '<div class="card text-center alert-success">✨ סיימנו! הגוף רפוי ומשוחרר.</div>';
      return;
    }
    if (phase === "tense") {
      container.innerHTML = `<div class="card"><div style="font-weight:600;margin-bottom:0.35rem;">שלב ${step + 1}/${groups.length}: ${groups[step][0]}</div><div class="text-secondary text-sm">${groups[step][1]}</div></div>`;
      phase = "release";
      guidedTimer = setTimeout(showStep, 5000);
    } else {
      container.innerHTML = `<div class="card"><div style="font-weight:600;margin-bottom:0.35rem;">😮‍💨 שחרור</div><div class="text-secondary text-sm">${groups[step][2]}</div></div>`;
      phase = "tense";
      step++;
      guidedTimer = setTimeout(showStep, 10000);
    }
  }
  showStep();
}

function stopGuided() {
  if (guidedTimer) clearTimeout(guidedTimer);
  guidedTimer = null;
  document.getElementById("panicMain").style.display = "block";
  document.getElementById("panicGuided").style.display = "none";
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------
async function loadAnalytics() {
  const container = document.getElementById("analyticsContent");
  container.innerHTML = '<div class="text-center text-muted" style="padding:2rem;"><div class="spinner"></div></div>';

  try {
    const data = await api("/api/analytics");

    if (!data.has_data) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📊</div>
          <div>עדיין אין נתונים</div>
          <div class="text-sm text-muted mt-1">התחל לדווח כדי לראות דפוסים!</div>
        </div>`;
      return;
    }

    let html = `
      <div class="gap-grid mb-1">
        <div class="stat-card">
          <div class="stat-icon" style="background:var(--sf-primary-bg);color:var(--sf-primary);">📊</div>
          <div class="stat-number">${data.avg_anxiety}</div>
          <div class="stat-label">ממוצע חרדה</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:var(--sf-teal-bg);color:var(--sf-teal);">📝</div>
          <div class="stat-number">${data.total_reports}</div>
          <div class="stat-label">סה"כ דיווחים</div>
        </div>
      </div>
      <div class="gap-grid mb-2">
        <div class="stat-card">
          <div class="stat-icon" style="background:var(--sf-red-bg);color:var(--sf-red);">📈</div>
          <div class="stat-number">${data.max_anxiety}</div>
          <div class="stat-label">מקסימום</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:var(--sf-green-bg);color:var(--sf-green);">📉</div>
          <div class="stat-number">${data.min_anxiety}</div>
          <div class="stat-label">מינימום</div>
        </div>
      </div>`;

    // Trend
    if (data.trend) {
      const trendIcon = data.trend.direction === "down" ? "📉" : data.trend.direction === "up" ? "📈" : "➡️";
      const trendText = data.trend.direction === "down" ? "ירידה" : data.trend.direction === "up" ? "עלייה" : "יציבות";
      const trendClass = data.trend.direction === "down" ? "alert-success" : data.trend.direction === "up" ? "alert-warning" : "";
      html += `<div class="alert ${trendClass} mb-1">${trendIcon} מגמה: ${trendText} ברמת החרדה (${data.trend.change > 0 ? "+" : ""}${data.trend.change})</div>`;
    }

    // Report types
    html += `<div class="card mb-1">
      <div style="font-weight:600;margin-bottom:0.5rem;">סוגי דיווחים</div>
      <div class="text-sm text-secondary">מהיר: ${data.quick_reports} | מלא: ${data.full_reports}</div>
    </div>`;

    // Location stats
    if (data.location_stats.length) {
      html += `<div class="card mb-1"><div style="font-weight:600;margin-bottom:0.5rem;">📍 מיקומים</div>`;
      data.location_stats.forEach((l) => {
        html += `<div class="text-sm text-secondary" style="margin-bottom:0.25rem;">${esc(l.location)}: ${l.count} פעמים — ממוצע ${l.avg_anxiety}</div>`;
      });
      html += "</div>";
    }

    // People stats
    if (data.people_stats.length) {
      html += `<div class="card mb-1"><div style="font-weight:600;margin-bottom:0.5rem;">👥 מצבים חברתיים</div>`;
      data.people_stats.forEach((p) => {
        html += `<div class="text-sm text-secondary" style="margin-bottom:0.25rem;">${esc(p.people)}: ${p.count} פעמים — ממוצע ${p.avg_anxiety}</div>`;
      });
      html += "</div>";
    }

    // Simple chart (text-based bar chart)
    if (data.chart_data && data.chart_data.length > 1) {
      html += `<div class="card mb-1"><div style="font-weight:600;margin-bottom:0.5rem;">📈 מגמת חרדה</div>`;
      const last10 = data.chart_data.slice(-10);
      last10.forEach((d) => {
        const pct = (d.level / 10) * 100;
        const color = d.level >= 7 ? "var(--sf-red)" : d.level >= 4 ? "var(--sf-amber)" : "var(--sf-green)";
        html += `<div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.25rem;">
          <span class="text-sm text-muted" style="min-width:25px;">${d.level}</span>
          <div style="flex:1;height:8px;background:var(--sf-progress-bg);border-radius:4px;overflow:hidden;">
            <div style="width:${pct}%;height:100%;background:${color};border-radius:4px;"></div>
          </div>
        </div>`;
      });
      html += "</div>";
    }

    html += `<div class="alert mt-1">💡 המשך לדווח כדי לקבל תובנות מדויקות יותר!</div>`;

    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<div class="alert alert-destructive">שגיאה בטעינת הנתונים</div>';
  }
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
async function loadSettings() {
  try {
    const settings = await api("/api/settings");
    const toggle = document.getElementById("reminderToggle");
    if (settings.daily_reminder) toggle.classList.add("active");
    else toggle.classList.remove("active");
  } catch (e) {
    /* silent */
  }
}

async function toggleReminder() {
  const toggle = document.getElementById("reminderToggle");
  const isActive = toggle.classList.contains("active");
  toggle.classList.toggle("active");
  await api("/api/settings", { method: "POST", body: { daily_reminder: !isActive } });
}

async function exportData() {
  try {
    const data = await api("/api/settings/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `shalva_data_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert("שגיאה בייצוא");
  }
}

function confirmReset() {
  if (confirm("⚠️ האם אתה בטוח?\n\nפעולה זו תמחק את כל הנתונים שלך.\nזה בלתי הפיך!")) {
    resetData();
  }
}

async function resetData() {
  await api("/api/settings/reset", { method: "POST" });
  alert("✅ הנתונים נמחקו בהצלחה!");
  showScreen("screen-home");
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  await initSession();
  initQuickReport();
  initFullReport();
  loadSettings();

  // Reset forms when navigating away
  const origShowScreen = showScreen;
  showScreen = function (id) {
    // Reset forms when leaving
    if (currentScreen === "screen-quick-report" && id !== "screen-quick-report") resetQuickReport();
    if (currentScreen === "screen-full-report" && id !== "screen-full-report") resetFullReport();
    if (currentScreen === "screen-venting" && id !== "screen-venting") resetVenting();
    if (currentScreen === "screen-panic" && id !== "screen-panic") { stopBreathing(); stopGuided(); }
    origShowScreen(id);
  };
});
