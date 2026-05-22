// ==================== HOW-TO COMPONENT ====================
import { t } from "../data/translations.js";

export function renderHowto() {
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
