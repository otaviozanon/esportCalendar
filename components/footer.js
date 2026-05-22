// ==================== FOOTER COMPONENT ====================
import { t } from "./data/translations.js";

export function renderFooter() {
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
