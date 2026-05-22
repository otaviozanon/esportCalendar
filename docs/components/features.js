// ==================== FEATURES COMPONENT ====================
import { features } from "../data/games.js";
import { t } from "../data/translations.js";

export function renderFeatures() {
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
