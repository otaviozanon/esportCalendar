// ==================== EFFECTS UTILITIES ====================

// Inicializa animações GSAP
export function initAnimations() {
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

// Inicializa efeito de mouse glow
export function initMouseGlow() {
  const mouseGlow = document.getElementById("mouse-glow");
  if (!mouseGlow) return;

  let mouseX = 0;
  let mouseY = 0;
  let glowX = 0;
  let glowY = 0;

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
