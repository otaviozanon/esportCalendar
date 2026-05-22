// ==================== NAVBAR COMPONENT ====================
import { t, currentLang } from "../data/translations.js";

export function renderNavbar() {
  document.getElementById("navbar").innerHTML = `
    <nav class="fixed top-0 left-0 right-0 z-50 glass border-b border-[#222]">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-lg bg-[#ea580c] flex items-center justify-center">
              <i data-lucide="calendar-check" class="w-5 h-5 text-white"></i>
            </div>
            <span class="text-lg font-semibold">Esport Calendar BR</span>
          </div>
          <div class="hidden md:flex items-center gap-6">
            <a href="#games" class="text-sm text-[#a3a3a3] hover:text-white transition-colors" data-i18n="nav_games">${t("nav_games")}</a>
            <a href="#features" class="text-sm text-[#a3a3a3] hover:text-white transition-colors" data-i18n="nav_features">${t("nav_features")}</a>
            <a href="#howto" class="text-sm text-[#a3a3a3] hover:text-white transition-colors" data-i18n="nav_howto">${t("nav_howto")}</a>
            <a href="https://github.com/otaviozanon/esportCalendar" target="_blank" class="flex items-center gap-2 text-sm text-[#a3a3a3] hover:text-white transition-colors">
              <i data-lucide="github" class="w-4 h-4"></i>
              GitHub
            </a>
            <button id="lang-toggle" class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-[#1f1f1f] hover:bg-[#262626] border border-[#404040] transition-colors text-xs font-medium">
              <i data-lucide="languages" class="w-3.5 h-3.5"></i>
              <span>${currentLang.toUpperCase()}</span>
            </button>
          </div>
          <button id="mobile-menu-btn" class="md:hidden p-2 rounded-lg hover:bg-[#1a1a1a] transition-colors">
            <i data-lucide="menu" class="w-5 h-5"></i>
          </button>
        </div>
      </div>
    </nav>
    
    <div id="mobile-menu" class="fixed inset-0 z-40 glass hidden md:hidden" style="top: 64px;">
      <div class="flex flex-col p-6 gap-4">
        <a href="#games" class="text-base text-[#a3a3a3] hover:text-white transition-colors" data-i18n="nav_games">${t("nav_games")}</a>
        <a href="#features" class="text-base text-[#a3a3a3] hover:text-white transition-colors" data-i18n="nav_features">${t("nav_features")}</a>
        <a href="#howto" class="text-base text-[#a3a3a3] hover:text-white transition-colors" data-i18n="nav_howto">${t("nav_howto")}</a>
        <a href="https://github.com/otaviozanon/esportCalendar" target="_blank" class="flex items-center gap-2 text-base text-[#a3a3a3] hover:text-white transition-colors">
          <i data-lucide="github" class="w-4 h-4"></i>
          GitHub
        </a>
        <button id="lang-toggle-mobile" class="flex items-center gap-2 px-3 py-2 rounded-md bg-[#1f1f1f] hover:bg-[#262626] border border-[#404040] transition-colors text-sm font-medium w-fit">
          <i data-lucide="languages" class="w-4 h-4"></i>
          <span>${currentLang.toUpperCase()}</span>
        </button>
      </div>
    </div>
  `;
}
