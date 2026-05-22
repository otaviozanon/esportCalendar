// ==================== PROFESSIONAL MODULAR STRUCTURE ====================
// Este arquivo é o ponto de entrada principal que orquestra todos os componentes

// Importa componentes
import { renderNavbar } from "./components/navbar.js";
import { renderHero } from "./components/hero.js";
import { renderGames } from "./components/games.js";
import { renderFeatures } from "./components/features.js";
import { renderHowto } from "./components/howto.js";
import { renderFooter } from "./components/footer.js";

// Importa utilitários
import { loadCalendarData, loadLastUpdate } from "./utils/api.js";
import { initAnimations, initMouseGlow } from "./utils/effects.js";
import { setupEventListeners } from "./utils/events.js";
import { setupLanguageToggle } from "./utils/i18n.js";

// ==================== RENDER ALL COMPONENTS ====================
function renderAll() {
  console.log("?? Starting render...");

  // Renderiza todos os componentes
  renderNavbar();
  renderHero();
  renderGames();
  renderFeatures();
  renderHowto();
  renderFooter();

  // Inicializa ícones Lucide
  setTimeout(() => {
    if (typeof lucide !== "undefined") {
      lucide.createIcons();
      console.log("? Icons initialized");

      // Debug: verifica ícones chevron
      const chevrons = document.querySelectorAll(
        '[data-lucide="chevron-down"]',
      );
      console.log(`?? Found ${chevrons.length} chevron icons`);
    } else {
      console.error("? Lucide not loaded");
    }
  }, 100);

  // Carrega dados da API
  loadCalendarData();
  loadLastUpdate();

  // Configura event listeners
  setTimeout(() => {
    setupEventListeners();
    setupLanguageToggle();
  }, 200);

  // Inicializa animações
  setTimeout(() => {
    initAnimations();
  }, 300);
}

// ==================== INIT ====================
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    renderAll();
    initMouseGlow();
  });
} else {
  renderAll();
  initMouseGlow();
}
