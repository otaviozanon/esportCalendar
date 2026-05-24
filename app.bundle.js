// ==================== BUNDLED APP ====================
// Tudo consolidado em um arquivo único para GitHub Pages

// ==================== DATA: TRANSLATIONS ====================
const translations = {
  pt: {
    // Navbar
    nav_games: "Jogos",
    nav_features: "Recursos",
    nav_howto: "Como Usar",

    // Hero
    hero_badge: "Atualizado a cada 48 minutos",
    hero_title_1: "Nunca mais perca",
    hero_title_2: "uma partida",
    hero_subtitle:
      "Calendário automático dos melhores times brasileiros de esports.",
    hero_games: "Counter Strike 2, Valorant, League of Legends e Rocket League",
    hero_download: "Baixar Calendário",
    hero_add: "Adicionar ao Calendário",
    hero_stat1_title: "Times Brasileiros",
    hero_stat1_desc: "Focado em times brasileiros",
    hero_stat2_title: "Lembrete Automático",
    hero_stat2_desc: "15 minutos antes da partida",
    hero_stat3_title: "Sempre Atualizado",
    hero_stat3_desc: "Atualização a cada 48 minutos",

    // Games
    games_title: "Jogos Suportados",
    games_subtitle: "Acompanhe os melhores times brasileiros",
    games_cs2: "Counter-Strike 2",
    games_cs2_desc: "Partida do dia atual e 3 dias à frente",
    games_valorant: "Valorant",
    games_valorant_desc: "Partidas do dia atual",
    games_lol: "League of Legends",
    games_lol_desc: "Partidas do dia atual",
    games_rocket: "Rocket League",
    games_rocket_desc: "Partidas do dia atual",
    games_teams_supported: "Times suportados",

    // Features
    features_title: "Por que usar?",
    features_subtitle: "Recursos principais do calendário",
    feature1_title: "Totalmente Automático",
    feature1_desc: "Atualização contínua via GitHub Actions",
    feature2_title: "Notificações Inteligentes",
    feature2_desc: "Lembrete 15min antes de cada partida",
    feature3_title: "Funciona em Qualquer Lugar",
    feature3_desc: "Google Calendar, Outlook e Apple Calendar",
    feature4_title: "Limpeza Automática",
    feature4_desc: "Remove partidas antigas automaticamente",

    // How-to
    howto_title: "Como Adicionar",
    howto_subtitle: "Escolha sua plataforma",
    howto_tab_google: "Google",
    howto_tab_outlook: "Outlook",
    howto_tab_apple: "Apple",
    howto_step1: "Copie a URL",
    howto_step2_google: "Abra Google Calendar",
    howto_step2_outlook: "Baixe o .ics",
    howto_step2_apple: "Arquivo → Nova Assinatura",
    howto_step3_google: "Adicione via URL",
    howto_step3_google_desc: 'Clique no + → "De URL" → Cole',
    howto_step3_outlook: "Abra o arquivo",
    howto_step3_outlook_desc: "Duplo clique no calendar.ics",
    howto_step3_apple: "Cole e Assinar",
    howto_step4_outlook: "Salvar",
    howto_step4_outlook_desc: '"Salvar & Fechar"',
    howto_download_btn: 'Botão "Baixar Calendário"',

    // Footer
    footer_tagline: "Feito com ❤️ para a comunidade brasileira de esports",
    footer_opensource: "Open Source",
    footer_github_btn: "Veja no GitHub",
    footer_contribute: "Contribua com o projeto",
    footer_last_update: "Última atualização:",
    footer_copyright: "Otavio Zanon - 2026",
  },

  en: {
    // Navbar
    nav_games: "Games",
    nav_features: "Features",
    nav_howto: "How to Use",

    // Hero
    hero_badge: "Updated every 48 minutes",
    hero_title_1: "Never miss",
    hero_title_2: "a match again",
    hero_subtitle: "Automatic calendar for the best Brazilian esports teams.",
    hero_games:
      "Counter Strike 2, Valorant, League of Legends and Rocket League",
    hero_download: "Download Calendar",
    hero_add: "Add to Calendar",
    hero_stat1_title: "Brazilian Teams",
    hero_stat1_desc: "Focused on Brazilian teams",
    hero_stat2_title: "Auto Reminder",
    hero_stat2_desc: "15 minutes before match",
    hero_stat3_title: "Always Updated",
    hero_stat3_desc: "Updates every 48 minutes",

    // Games
    games_title: "Supported Games",
    games_subtitle: "Follow the best Brazilian teams",
    games_cs2: "Counter-Strike 2",
    games_cs2_desc: "Current day matches + 3 days ahead",
    games_valorant: "Valorant",
    games_valorant_desc: "Current day matches",
    games_lol: "League of Legends",
    games_lol_desc: "Current day matches",
    games_rocket: "Rocket League",
    games_rocket_desc: "Current day matches",
    games_teams_supported: "Supported teams",

    // Features
    features_title: "Why use it?",
    features_subtitle: "Main calendar features",
    feature1_title: "Fully Automatic",
    feature1_desc: "Continuous updates via GitHub Actions",
    feature2_title: "Smart Notifications",
    feature2_desc: "15min reminder before each match",
    feature3_title: "Works Everywhere",
    feature3_desc: "Google Calendar, Outlook and Apple Calendar",
    feature4_title: "Auto Cleanup",
    feature4_desc: "Removes old matches automatically",

    // How-to
    howto_title: "How to Add",
    howto_subtitle: "Choose your platform",
    howto_tab_google: "Google",
    howto_tab_outlook: "Outlook",
    howto_tab_apple: "Apple",
    howto_step1: "Copy the URL",
    howto_step2_google: "Open Google Calendar",
    howto_step2_outlook: "Download the .ics",
    howto_step2_apple: "File → New Subscription",
    howto_step3_google: "Add via URL",
    howto_step3_google_desc: 'Click + → "From URL" → Paste',
    howto_step3_outlook: "Open the file",
    howto_step3_outlook_desc: "Double click calendar.ics",
    howto_step3_apple: "Paste and Subscribe",
    howto_step4_outlook: "Save",
    howto_step4_outlook_desc: '"Save & Close"',
    howto_download_btn: '"Download Calendar" button',

    // Footer
    footer_tagline: "Made with ❤️ for the Brazilian esports community",
    footer_opensource: "Open Source",
    footer_github_btn: "View on GitHub",
    footer_contribute: "Contribute to the project",
    footer_last_update: "Last update:",
    footer_copyright: "Otavio Zanon - 2026",
  },
};

// Estado atual do idioma (default: pt)
let currentLang = localStorage.getItem("language") || "pt";

// Função para trocar idioma
function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem("language", lang);
}

// Função para pegar tradução
function t(key) {
  return translations[currentLang][key] || key;
}

// ==================== DATA: GAMES ====================
const gamesData = [
  {
    id: "cs2",
    icon: "crosshair",
    name: "Counter-Strike 2",
    desc: "Partida do dia atual e 3 dias a frente",
    teams: [],
  },
  {
    id: "valorant",
    icon: "sparkles",
    name: "Valorant",
    desc: "Partidas do dia atual",
    teams: [],
  },
  {
    id: "lol",
    icon: "swords",
    name: "League of Legends",
    desc: "Partidas do dia atual",
    teams: [],
  },
  {
    id: "rocket",
    icon: "car",
    name: "Rocket League",
    desc: "Partidas do dia atual",
    teams: [],
  },
];

async function loadTeamsData() {
  try {
    const res = await fetch("./scripts/data/teams.json");
    if (!res.ok) {
      console.warn("teams.json not available, using empty teams");
      return;
    }
    const data = await res.json();
    for (const game of gamesData) {
      if (data[game.id]) {
        game.teams = data[game.id];
      }
    }
  } catch (err) {
    console.error("Failed to load teams.json:", err);
  }
}

const features = [
  { id: "feature1", icon: "bot" },
  { id: "feature2", icon: "bell-ring" },
  { id: "feature3", icon: "smartphone" },
  { id: "feature4", icon: "trash-2" },
];

// ==================== UTILS: API ====================
async function loadCalendarData() {
  try {
    const res = await fetch("./calendar.ics");
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

async function loadLastUpdate() {
  try {
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
    const stateRes = await fetch("./scripts/data/state.json");
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

// ==================== UTILS: EFFECTS ====================
function initAnimations() {
  if (typeof gsap !== "undefined") {
    gsap.registerPlugin(ScrollTrigger);
    gsap.from(".group.glass", {
      scrollTrigger: { trigger: "#games", start: "top 80%" },
      y: 50,
      opacity: 0,
      duration: 0.8,
      stagger: 0.1,
    });
    gsap.from("#features .glass", {
      scrollTrigger: { trigger: "#features", start: "top 80%" },
      y: 50,
      opacity: 0,
      duration: 0.8,
      stagger: 0.1,
    });
  }
}

function initMouseGlow() {
  const mouseGlow = document.getElementById("mouse-glow");
  if (!mouseGlow) return;
  let mouseX = 0,
    mouseY = 0,
    glowX = 0,
    glowY = 0;
  document.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    mouseGlow.style.opacity = "1";
  });
  document.addEventListener("mouseleave", () => {
    mouseGlow.style.opacity = "0";
  });
  function animate() {
    glowX += (mouseX - glowX) * 0.1;
    glowY += (mouseY - glowY) * 0.1;
    mouseGlow.style.left = `${glowX}px`;
    mouseGlow.style.top = `${glowY}px`;
    requestAnimationFrame(animate);
  }
  animate();
}

// ==================== UTILS: EVENTS ====================
function setupEventListeners() {
  const mobileBtn = document.getElementById("mobile-menu-btn");
  const mobileMenu = document.getElementById("mobile-menu");
  if (mobileBtn) {
    mobileBtn.addEventListener("click", () => {
      mobileMenu.classList.toggle("hidden");
    });
  }

  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const target = document.querySelector(a.getAttribute("href"));
      if (target) {
        target.scrollIntoView({ behavior: "smooth" });
        if (mobileMenu) mobileMenu.classList.add("hidden");
      }
    });
  });

  document.querySelectorAll(".teams-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const game = btn.dataset.game;
      const list = document.querySelector(`.teams-list[data-game="${game}"]`);
      const card = document.querySelector(`.game-card[data-game="${game}"]`);
      const isOpen = list.classList.contains("open");

      if (isOpen) {
        list.classList.remove("open");
        card.classList.remove("active");
        btn.setAttribute("aria-expanded", "false");
        setTimeout(() => {
          list.style.display = "none";
        }, 600);
      } else {
        list.style.display = "flex";
        card.classList.add("active");
        list.offsetHeight;
        list.classList.add("open");
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll(".tab-btn").forEach((b) => {
        b.classList.remove("active", "border-[#ea580c]", "text-white");
        b.classList.add("border-transparent", "text-[#737373]");
      });
      document
        .querySelectorAll(".tab-content")
        .forEach((c) => c.classList.add("hidden"));
      btn.classList.add("active", "border-[#ea580c]", "text-white");
      btn.classList.remove("border-transparent", "text-[#737373]");
      const content = document.querySelector(`.tab-content[data-tab="${tab}"]`);
      if (content) content.classList.remove("hidden");
    });
  });

  document.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const url = btn.dataset.url;
      try {
        await navigator.clipboard.writeText(url);
        const icon = btn.querySelector("i");
        if (icon) {
          icon.setAttribute("data-lucide", "check");
          lucide.createIcons();
          setTimeout(() => {
            icon.setAttribute("data-lucide", "copy");
            lucide.createIcons();
          }, 2000);
        }
      } catch (err) {
        console.error("Copy failed:", err);
      }
    });
  });

  const howBtn = document.getElementById("how-btn");
  if (howBtn) {
    howBtn.addEventListener("click", () => {
      document.getElementById("howto")?.scrollIntoView({ behavior: "smooth" });
    });
  }
}

// ==================== COMPONENTS: NAVBAR ====================
function renderNavbar() {
  document.getElementById("navbar").innerHTML = `
    <nav class="fixed top-0 left-0 right-0 z-50 glass border-b border-[#222]">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-lg bg-[#ea580c] flex items-center justify-center">
              <i data-lucide="calendar-check" class="w-5 h-5 text-white"></i>
            </div>
            <span class="font-semibold text-lg">Esport Calendar BR</span>
          </div>
          <div class="hidden md:flex items-center gap-6">
            <a href="#games" class="text-sm text-[#a3a3a3] hover:text-white transition-colors" data-i18n="nav_games">${t("nav_games")}</a>
            <a href="#features" class="text-sm text-[#a3a3a3] hover:text-white transition-colors" data-i18n="nav_features">${t("nav_features")}</a>
            <a href="#howto" class="text-sm text-[#a3a3a3] hover:text-white transition-colors" data-i18n="nav_howto">${t("nav_howto")}</a>
            <button id="lang-toggle" class="px-3 py-1.5 text-xs border border-[#404040] hover:border-[#525252] rounded transition-colors">${currentLang === "pt" ? "🇧🇷 PT" : "🇺🇸 EN"}</button>
          </div>
          <button id="mobile-menu-btn" class="md:hidden p-2"><i data-lucide="menu" class="w-5 h-5"></i></button>
        </div>
      </div>
      <div id="mobile-menu" class="hidden md:hidden border-t border-[#222] bg-[#0d0d0d]">
        <div class="px-4 py-3 space-y-2">
          <a href="#games" class="block py-2 text-sm text-[#a3a3a3]" data-i18n="nav_games">${t("nav_games")}</a>
          <a href="#features" class="block py-2 text-sm text-[#a3a3a3]" data-i18n="nav_features">${t("nav_features")}</a>
          <a href="#howto" class="block py-2 text-sm text-[#a3a3a3]" data-i18n="nav_howto">${t("nav_howto")}</a>
          <button id="lang-toggle-mobile" class="w-full px-3 py-2 text-xs border border-[#404040] rounded">${currentLang === "pt" ? "🇧🇷 PT" : "🇺🇸 EN"}</button>
        </div>
      </div>
    </nav>
  `;
}

// ==================== COMPONENTS: HERO ====================
function renderHero() {
  document.getElementById("hero").innerHTML = `
    <div class="relative min-h-screen flex items-center justify-center pt-16 px-4">
      <div class="max-w-5xl mx-auto text-center">
        <div class="mb-6 inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#404040] bg-[#1f1f1f] text-xs text-[#a3a3a3]">
          <div class="w-1.5 h-1.5 rounded-full bg-[#ea580c] animate-pulse"></div>
          <span data-i18n="hero_badge">${t("hero_badge")}</span>
        </div>
        <h1 class="text-5xl md:text-6xl lg:text-7xl font-bold mb-6 leading-tight tracking-tight">
          <span data-i18n="hero_title_1">${t("hero_title_1")}</span><br>
          <span class="text-[#a3a3a3]" data-i18n="hero_title_2">${t("hero_title_2")}</span>
        </h1>
        <p class="text-lg md:text-xl text-[#737373] mb-12 max-w-2xl mx-auto leading-relaxed">
          <span data-i18n="hero_subtitle">${t("hero_subtitle")}</span> <span class="font-bold text-[#d4d4d4]" data-i18n="hero_games">${t("hero_games")}</span>.
        </p>
        <div class="flex flex-col sm:flex-row gap-3 justify-center items-center mb-16">
          <a href="./calendar.ics" download class="flex items-center gap-2 px-6 py-3 bg-[#ea580c] hover:bg-[#c2410c] rounded-lg font-medium text-sm transition-all duration-200 hover:scale-105">
            <i data-lucide="download" class="w-4 h-4"></i>
            <span data-i18n="hero_download">${t("hero_download")}</span>
          </a>
          <button id="how-btn" class="flex items-center gap-2 px-6 py-3 border border-[#404040] hover:border-[#525252] hover:bg-[#1f1f1f] rounded-lg font-medium text-sm transition-all duration-200">
            <i data-lucide="plus-circle" class="w-4 h-4"></i>
            <span data-i18n="hero_add">${t("hero_add")}</span>
          </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl mx-auto">
          <div class="border border-[#404040] rounded-lg p-6 hover:border-[#525252] hover:shadow-lg transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
              <i data-lucide="flag" class="w-5 h-5 text-[#ea580c]"></i>
              <div class="text-sm font-semibold text-[#d4d4d4]" data-i18n="hero_stat1_title">${t("hero_stat1_title")}</div>
            </div>
            <div class="text-xs text-[#737373]" data-i18n="hero_stat1_desc">${t("hero_stat1_desc")}</div>
          </div>
          <div class="border border-[#404040] rounded-lg p-6 hover:border-[#525252] hover:shadow-lg transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
              <i data-lucide="bell" class="w-5 h-5 text-[#ea580c]"></i>
              <div class="text-sm font-semibold text-[#d4d4d4]" data-i18n="hero_stat2_title">${t("hero_stat2_title")}</div>
            </div>
            <div class="text-xs text-[#737373]" data-i18n="hero_stat2_desc">${t("hero_stat2_desc")}</div>
          </div>
          <div class="border border-[#404040] rounded-lg p-6 hover:border-[#525252] hover:shadow-lg transition-all duration-200">
            <div class="flex items-center gap-3 mb-2">
              <i data-lucide="refresh-cw" class="w-5 h-5 text-[#ea580c]"></i>
              <div class="text-sm font-semibold text-[#d4d4d4]" data-i18n="hero_stat3_title">${t("hero_stat3_title")}</div>
            </div>
            <div class="text-xs text-[#737373]" data-i18n="hero_stat3_desc">${t("hero_stat3_desc")}</div>
          </div>
        </div>
      </div>
    </div>
  `;
}

// ==================== COMPONENTS: GAMES ====================
function renderGames() {
  const cards = gamesData
    .map(
      (g) => `
    <div class="game-card border border-[#404040] rounded-lg p-6 transition-all duration-300" data-game="${g.id}">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-10 h-10 rounded-lg bg-[#262626] flex items-center justify-center">
          <i data-lucide="${g.icon}" class="w-5 h-5 text-[#ea580c]"></i>
        </div>
        <h3 class="text-lg font-bold text-[#a3a3a3]" data-i18n="games_${g.id}">${t(`games_${g.id}`)}</h3>
      </div>
      <p class="text-sm text-[#737373] mb-4" data-i18n="games_${g.id}_desc">${t(`games_${g.id}_desc`)}</p>
      <button class="teams-toggle w-full flex items-center justify-between py-2 px-3 rounded-md bg-[#1f1f1f] hover:bg-[#262626] transition-all duration-200 text-sm" data-game="${g.id}" aria-expanded="false">
        <span class="text-[#a3a3a3]"><span data-i18n="games_teams_supported">${t("games_teams_supported")}</span> (${g.teams.length})</span>
        <i data-lucide="chevron-down" class="w-4 h-4 text-[#737373]"></i>
      </button>
      <div class="teams-list mt-3" data-game="${g.id}" style="display: none;">
        ${g.teams.map((team) => `<span class="inline-block px-2 py-1 rounded border border-[#404040] text-xs text-[#a3a3a3] hover:border-[#ea580c] hover:text-[#ea580c] transition-colors cursor-pointer">${team}</span>`).join("")}
      </div>
    </div>
  `,
    )
    .join("");

  document.getElementById("games").innerHTML = `
    <div id="games" class="py-20 px-4">
      <div class="max-w-6xl mx-auto">
        <div class="mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-2" data-i18n="games_title">${t("games_title")}</h2>
          <p class="text-[#737373]" data-i18n="games_subtitle">${t("games_subtitle")}</p>
        </div>
        <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-4">${cards}</div>
      </div>
    </div>
  `;
}

// ==================== COMPONENTS: FEATURES ====================
function renderFeatures() {
  const cards = features
    .map(
      (f) => `
    <div class="border border-[#404040] rounded-lg p-6 hover:border-[#525252] hover:shadow-lg transition-all duration-300">
      <div class="w-10 h-10 rounded-lg bg-[#262626] flex items-center justify-center mb-4">
        <i data-lucide="${f.icon}" class="w-5 h-5 text-[#ea580c]"></i>
      </div>
      <h3 class="text-base font-semibold mb-2" data-i18n="${f.id}_title">${t(`${f.id}_title`)}</h3>
      <p class="text-sm text-[#737373]" data-i18n="${f.id}_desc">${t(`${f.id}_desc`)}</p>
    </div>
  `,
    )
    .join("");

  document.getElementById("features").innerHTML = `
    <div class="py-20 px-4 border-t border-[#404040]">
      <div class="max-w-5xl mx-auto">
        <div class="mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-2" data-i18n="features_title">${t("features_title")}</h2>
          <p class="text-[#737373]" data-i18n="features_subtitle">${t("features_subtitle")}</p>
        </div>
        <div class="grid md:grid-cols-2 gap-4">${cards}</div>
      </div>
    </div>
  `;
}

// ==================== COMPONENTS: HOWTO ====================
function renderHowto() {
  document.getElementById("howto").innerHTML = `
    <div class="py-20 px-4 border-t border-[#222]">
      <div class="max-w-4xl mx-auto">
        <div class="mb-12">
          <h2 class="text-3xl md:text-4xl font-bold mb-2" data-i18n="howto_title">${t("howto_title")}</h2>
          <p class="text-[#737373]" data-i18n="howto_subtitle">${t("howto_subtitle")}</p>
        </div>
        <div class="flex gap-2 mb-6 border-b border-[#404040]">
          <button class="tab-btn active px-4 py-2 text-sm font-medium border-b-2 border-[#ea580c] text-white transition-all duration-200" data-tab="google" data-i18n="howto_tab_google">${t("howto_tab_google")}</button>
          <button class="tab-btn px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#737373] hover:text-white transition-all duration-200" data-tab="outlook" data-i18n="howto_tab_outlook">${t("howto_tab_outlook")}</button>
          <button class="tab-btn px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#737373] hover:text-white transition-all duration-200" data-tab="apple" data-i18n="howto_tab_apple">${t("howto_tab_apple")}</button>
        </div>
        <div class="tab-content block" data-tab="google">
          <div class="border border-[#404040] rounded-lg p-6 space-y-5">
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-[#ea580c] flex items-center justify-center font-semibold text-sm flex-shrink-0">1</div>
              <div class="flex-1">
                <h3 class="font-semibold mb-2" data-i18n="howto_step1">${t("howto_step1")}</h3>
                <div class="flex gap-2">
                  <input type="text" readonly value="https://is.gd/EsportCalendar" class="flex-1 px-3 py-2 bg-[#1f1f1f] border border-[#404040] rounded text-xs font-mono">
                  <button class="copy-btn px-4 py-2 bg-[#ea580c] hover:bg-[#c2410c] rounded text-sm transition-all duration-200" data-url="https://is.gd/EsportCalendar">
                    <i data-lucide="copy" class="w-4 h-4"></i>
                  </button>
                </div>
              </div>
            </div>
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-[#ea580c] flex items-center justify-center font-semibold text-sm flex-shrink-0">2</div>
              <div>
                <h3 class="font-semibold mb-1" data-i18n="howto_step2_google">${t("howto_step2_google")}</h3>
                <p class="text-sm text-[#737373]"><a href="https://calendar.google.com" target="_blank" class="text-[#ea580c] hover:underline">calendar.google.com</a></p>
              </div>
            </div>
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-[#ea580c] flex items-center justify-center font-semibold text-sm flex-shrink-0">3</div>
              <div>
                <h3 class="font-semibold mb-1" data-i18n="howto_step3_google">${t("howto_step3_google")}</h3>
                <p class="text-sm text-[#737373]" data-i18n="howto_step3_google_desc">${t("howto_step3_google_desc")}</p>
              </div>
            </div>
          </div>
        </div>
        <div class="tab-content hidden" data-tab="outlook">
          <div class="border border-[#404040] rounded-lg p-6 space-y-5">
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-[#ea580c] flex items-center justify-center font-semibold text-sm flex-shrink-0">1</div>
              <div><h3 class="font-semibold mb-1" data-i18n="howto_step2_outlook">${t("howto_step2_outlook")}</h3><p class="text-sm text-[#737373]" data-i18n="howto_download_btn">${t("howto_download_btn")}</p></div>
            </div>
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-[#ea580c] flex items-center justify-center font-semibold text-sm flex-shrink-0">2</div>
              <div><h3 class="font-semibold mb-1" data-i18n="howto_step3_outlook">${t("howto_step3_outlook")}</h3><p class="text-sm text-[#737373]" data-i18n="howto_step3_outlook_desc">${t("howto_step3_outlook_desc")}</p></div>
            </div>
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-[#ea580c] flex items-center justify-center font-semibold text-sm flex-shrink-0">3</div>
              <div><h3 class="font-semibold mb-1" data-i18n="howto_step4_outlook">${t("howto_step4_outlook")}</h3><p class="text-sm text-[#737373]" data-i18n="howto_step4_outlook_desc">${t("howto_step4_outlook_desc")}</p></div>
            </div>
          </div>
        </div>
        <div class="tab-content hidden" data-tab="apple">
          <div class="border border-[#404040] rounded-lg p-6 space-y-5">
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-[#ea580c] flex items-center justify-center font-semibold text-sm flex-shrink-0">1</div>
              <div class="flex-1">
                <h3 class="font-semibold mb-2" data-i18n="howto_step1">${t("howto_step1")}</h3>
                <div class="flex gap-2">
                  <input type="text" readonly value="https://is.gd/EsportCalendar" class="flex-1 px-3 py-2 bg-[#1f1f1f] border border-[#404040] rounded text-xs font-mono">
                  <button class="copy-btn px-4 py-2 bg-[#ea580c] hover:bg-[#c2410c] rounded text-sm transition-all duration-200" data-url="https://is.gd/EsportCalendar">
                    <i data-lucide="copy" class="w-4 h-4"></i>
                  </button>
                </div>
              </div>
            </div>
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-[#ea580c] flex items-center justify-center font-semibold text-sm flex-shrink-0">2</div>
              <div><h3 class="font-semibold mb-1" data-i18n="howto_step2_apple">${t("howto_step2_apple")}</h3></div>
            </div>
            <div class="flex gap-4">
              <div class="w-8 h-8 rounded-full bg-[#ea580c] flex items-center justify-center font-semibold text-sm flex-shrink-0">3</div>
              <div><h3 class="font-semibold mb-1" data-i18n="howto_step3_apple">${t("howto_step3_apple")}</h3></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

// ==================== COMPONENTS: FOOTER ====================
function renderFooter() {
  document.getElementById("footer").innerHTML = `
    <div class="py-16 px-4 border-t border-[#404040]">
      <div class="max-w-6xl mx-auto">
        <div class="grid md:grid-cols-2 gap-12 mb-8">
          <div>
            <div class="flex items-center gap-2 mb-3">
              <div class="w-8 h-8 rounded-lg bg-[#ea580c] flex items-center justify-center">
                <i data-lucide="calendar-check" class="w-4 h-4 text-white"></i>
              </div>
              <span class="font-semibold">Esport Calendar BR</span>
            </div>
            <p class="text-sm text-[#737373]" data-i18n="footer_tagline">${t("footer_tagline")}</p>
          </div>
          <div>
            <h3 class="font-semibold mb-3 text-sm" data-i18n="footer_opensource">${t("footer_opensource")}</h3>
            <a href="https://github.com/otaviozanon/esportCalendar" target="_blank" class="inline-flex items-center gap-2 px-4 py-2 border border-[#404040] hover:border-[#525252] hover:bg-[#1f1f1f] rounded-lg transition-all duration-200 text-sm mb-3">
              <i data-lucide="star" class="w-4 h-4 text-[#ea580c]"></i> <span data-i18n="footer_github_btn">${t("footer_github_btn")}</span>
            </a>
            <p class="text-xs text-[#737373]" data-i18n="footer_contribute">${t("footer_contribute")}</p>
          </div>
        </div>
        <div class="text-center text-xs text-[#737373] pt-8 border-t border-[#404040]">
          <p><span data-i18n="footer_last_update">${t("footer_last_update")}</span> <span id="last-update" class="text-[#ea580c] font-mono">...</span></p>
          <p class="mt-2" data-i18n="footer_copyright">${t("footer_copyright")}</p>
        </div>
      </div>
    </div>
  `;
}

// ==================== I18N: LANGUAGE TOGGLE ====================
function toggleLanguage() {
  const newLang = currentLang === "pt" ? "en" : "pt";
  setLanguage(newLang);
  renderAll();
  setTimeout(() => {
    if (typeof lucide !== "undefined") {
      lucide.createIcons();
    }
  }, 50);
}

function setupLanguageToggle() {
  const langToggle = document.getElementById("lang-toggle");
  if (langToggle) {
    langToggle.addEventListener("click", toggleLanguage);
  }
  const langToggleMobile = document.getElementById("lang-toggle-mobile");
  if (langToggleMobile) {
    langToggleMobile.addEventListener("click", toggleLanguage);
  }
}

// ==================== RENDER ALL ====================
function renderAll() {
  console.log("🚀 Starting render...");
  renderNavbar();
  renderHero();
  renderGames();
  renderFeatures();
  renderHowto();
  renderFooter();

  setTimeout(() => {
    if (typeof lucide !== "undefined") {
      lucide.createIcons();
      console.log("✅ Icons initialized");
    } else {
      console.error("❌ Lucide not loaded");
    }
  }, 100);

  loadCalendarData();
  loadLastUpdate();

  setTimeout(() => {
    setupEventListeners();
    setupLanguageToggle();
  }, 200);

  setTimeout(() => {
    initAnimations();
  }, 300);
}

// ==================== INIT ====================
async function init() {
  await loadTeamsData();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      renderAll();
      initMouseGlow();
    });
  } else {
    renderAll();
    initMouseGlow();
  }
}

init();
