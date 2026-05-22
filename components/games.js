// ==================== GAMES COMPONENT ====================
import { gamesData } from "./data/games.js";
import { t } from "./data/translations.js";

export function renderGames() {
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
                ${g.teams.map((t) => `<span class="inline-block px-2 py-1 rounded border border-[#404040] text-xs text-[#a3a3a3] hover:border-[#ea580c] hover:text-[#ea580c] transition-colors cursor-pointer">${t}</span>`).join("")}
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
