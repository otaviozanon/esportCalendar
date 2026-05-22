// ==================== I18N UTILITIES ====================
import { setLanguage, currentLang } from "./data/translations.js";
import { renderNavbar } from "./components/navbar.js";
import { renderHero } from "./components/hero.js";
import { renderGames } from "./components/games.js";
import { renderFeatures } from "./components/features.js";
import { renderHowto } from "./components/howto.js";
import { renderFooter } from "./components/footer.js";

// Função para alternar idioma
export function toggleLanguage() {
  const newLang = currentLang === "pt" ? "en" : "pt";
  setLanguage(newLang);
  
  // Re-renderiza todos os componentes
  renderAll();
  
  // Re-inicializa ícones Lucide
  setTimeout(() => {
    if (typeof lucide !== "undefined") {
      lucide.createIcons();
    }
  }, 50);
}

// Função para re-renderizar tudo
function renderAll() {
  renderNavbar();
  renderHero();
  renderGames();
  renderFeatures();
  renderHowto();
  renderFooter();
}

// Configura event listeners para os botões de idioma
export function setupLanguageToggle() {
  // Desktop
  const langToggle = document.getElementById("lang-toggle");
  if (langToggle) {
    langToggle.addEventListener("click", toggleLanguage);
  }
  
  // Mobile
  const langToggleMobile = document.getElementById("lang-toggle-mobile");
  if (langToggleMobile) {
    langToggleMobile.addEventListener("click", toggleLanguage);
  }
}
