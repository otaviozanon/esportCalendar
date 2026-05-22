// ==================== EVENT LISTENERS ====================

export function setupEventListeners() {
  // Mobile menu
  const mobileBtn = document.getElementById("mobile-menu-btn");
  const mobileMenu = document.getElementById("mobile-menu");
  if (mobileBtn) {
    mobileBtn.addEventListener("click", () => {
      mobileMenu.classList.toggle("hidden");
    });
  }

  // Smooth scroll
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

  // Teams toggle
  document.querySelectorAll(".teams-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const game = btn.dataset.game;
      const list = document.querySelector(`.teams-list[data-game="${game}"]`);
      const card = document.querySelector(`.game-card[data-game="${game}"]`);
      const isOpen = list.classList.contains("open");

      console.log(`🎮 Clicked ${game}`);
      console.log(`📋 List element:`, list);
      console.log(`🃏 Card element:`, card);
      console.log(`📂 Is open:`, isOpen);

      if (isOpen) {
        // Close this dropdown
        list.classList.remove("open");
        card.classList.remove("active");
        btn.setAttribute("aria-expanded", "false");

        // Wait for animation to finish before hiding
        setTimeout(() => {
          list.style.display = "none";
        }, 600);

        console.log(`❌ Closed ${game}`);
      } else {
        // Open this dropdown
        list.style.display = "flex";
        card.classList.add("active");
        // Force reflow to trigger animation
        list.offsetHeight;
        list.classList.add("open");
        btn.setAttribute("aria-expanded", "true");

        console.log(`✅ Opened ${game}`);
      }
    });
  });

  // Tabs
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

  // Copy buttons
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

  // How button
  const howBtn = document.getElementById("how-btn");
  if (howBtn) {
    howBtn.addEventListener("click", () => {
      document.getElementById("howto")?.scrollIntoView({ behavior: "smooth" });
    });
  }
}
