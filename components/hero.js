// ==================== HERO COMPONENT ====================
import { t } from "../data/translations.js";

export function renderHero() {
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
