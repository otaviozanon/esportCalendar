// ==================== API UTILITIES ====================

// Carrega dados do calendário
export async function loadCalendarData() {
  try {
    const res = await fetch("../calendar.ics");
    const text = await res.text();
    const count = (text.match(/BEGIN:VEVENT/g) || []).length;
    const el = document.getElementById("events-count");
    if (el) animateCounter(el, 0, count, 2000);
  } catch (err) {
    console.error("Calendar load error:", err);
    const el = document.getElementById("events-count");
    if (el) el.textContent = "...";
  }
}

// Carrega última atualização do GitHub
export async function loadLastUpdate() {
  try {
    // Tenta pegar do GitHub API (último commit do calendar.ics)
    const apiUrl =
      "https://api.github.com/repos/otaviozanon/esportCalendar/commits?path=calendar.ics&page=1&per_page=1";
    const res = await fetch(apiUrl);

    if (res.ok) {
      const commits = await res.json();
      if (commits.length > 0) {
        const lastCommit = commits[0];
        const date = new Date(lastCommit.commit.author.date);
        const el = document.getElementById("last-update");
        if (el) {
          el.textContent = date.toLocaleString("pt-BR", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          });
        }
        return;
      }
    }

    // Fallback: tenta state.json
    const stateRes = await fetch("../state.json");
    const state = await stateRes.json();
    const dates = Object.values(state.last_run || {});
    if (dates.length > 0) {
      const mostRecent = dates.sort().reverse()[0];
      const date = new Date(mostRecent);
      const el = document.getElementById("last-update");
      if (el) el.textContent = date.toLocaleString("pt-BR");
    }
  } catch (err) {
    console.error("Last update load error:", err);
    const el = document.getElementById("last-update");
    if (el) el.textContent = "Indisponível";
  }
}

// Anima contador
function animateCounter(el, start, end, duration) {
  let startTime = null;
  function step(currentTime) {
    if (!startTime) startTime = currentTime;
    const progress = Math.min((currentTime - startTime) / duration, 1);
    const current = Math.floor(progress * (end - start) + start);
    el.textContent = current;
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
