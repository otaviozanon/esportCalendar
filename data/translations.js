// ==================== TRANSLATIONS ====================

export const translations = {
  pt: {
    // Navbar
    nav_games: "Jogos",
    nav_features: "Recursos",
    nav_howto: "Como Usar",
    
    // Hero
    hero_badge: "Atualizado a cada 48 minutos",
    hero_title_1: "Nunca mais perca",
    hero_title_2: "uma partida",
    hero_subtitle: "Calendário automático dos melhores times brasileiros de esports.",
    hero_games: "Counter Strike 2, Valorant, League of Legends e Rocket League",
    hero_download: "Baixar Calendário",
    hero_add: "Adicionar ao Calendário",
    hero_stat1_title: "Times Brasileiros",
    hero_stat1_desc: "Focado em times brasileiros",
    hero_stat2_title: "Lembrete Automático",
    hero_stat2_desc: "15 minutos antes da partida",
    hero_stat3_title: "Sempre Atualizado",
    hero_stat3_desc: "Atualização a cada 48 minutos",
    
    // Games
    games_title: "Jogos Suportados",
    games_subtitle: "Acompanhe os melhores times brasileiros",
    games_cs2: "Counter-Strike 2",
    games_cs2_desc: "Partida do dia atual e 3 dias à frente",
    games_valorant: "Valorant",
    games_valorant_desc: "Partidas do dia atual",
    games_lol: "League of Legends",
    games_lol_desc: "Partidas do dia atual",
    games_rocket: "Rocket League",
    games_rocket_desc: "Partidas do dia atual",
    games_teams_supported: "Times suportados",
    
    // Features
    features_title: "Por que usar?",
    features_subtitle: "Recursos principais do calendário",
    feature1_title: "Totalmente Automático",
    feature1_desc: "Atualização contínua via GitHub Actions",
    feature2_title: "Notificações Inteligentes",
    feature2_desc: "Lembrete 15min antes de cada partida",
    feature3_title: "Funciona em Qualquer Lugar",
    feature3_desc: "Google Calendar, Outlook e Apple Calendar",
    feature4_title: "Limpeza Automática",
    feature4_desc: "Remove partidas antigas automaticamente",
    
    // How-to
    howto_title: "Como Adicionar",
    howto_subtitle: "Escolha sua plataforma",
    howto_tab_google: "Google",
    howto_tab_outlook: "Outlook",
    howto_tab_apple: "Apple",
    howto_step1: "Copie a URL",
    howto_step2_google: "Abra Google Calendar",
    howto_step2_outlook: "Baixe o .ics",
    howto_step2_apple: "Arquivo → Nova Assinatura",
    howto_step3_google: "Adicione via URL",
    howto_step3_google_desc: 'Clique no + → "De URL" → Cole',
    howto_step3_outlook: "Abra o arquivo",
    howto_step3_outlook_desc: "Duplo clique no calendar.ics",
    howto_step3_apple: "Cole e Assinar",
    howto_step4_outlook: "Salvar",
    howto_step4_outlook_desc: '"Salvar & Fechar"',
    howto_download_btn: "Botão "Baixar Calendário"",
    
    // Footer
    footer_tagline: "Feito com ❤️ para a comunidade brasileira de esports",
    footer_opensource: "Open Source",
    footer_github_btn: "Veja no GitHub",
    footer_contribute: "Contribua com o projeto",
    footer_last_update: "Última atualização:",
    footer_copyright: "Otavio Zanon - 2026",
  },
  
  en: {
    // Navbar
    nav_games: "Games",
    nav_features: "Features",
    nav_howto: "How to Use",
    
    // Hero
    hero_badge: "Updated every 48 minutes",
    hero_title_1: "Never miss",
    hero_title_2: "a match again",
    hero_subtitle: "Automatic calendar for the best Brazilian esports teams.",
    hero_games: "Counter Strike 2, Valorant, League of Legends and Rocket League",
    hero_download: "Download Calendar",
    hero_add: "Add to Calendar",
    hero_stat1_title: "Brazilian Teams",
    hero_stat1_desc: "Focused on Brazilian teams",
    hero_stat2_title: "Auto Reminder",
    hero_stat2_desc: "15 minutes before match",
    hero_stat3_title: "Always Updated",
    hero_stat3_desc: "Updates every 48 minutes",
    
    // Games
    games_title: "Supported Games",
    games_subtitle: "Follow the best Brazilian teams",
    games_cs2: "Counter-Strike 2",
    games_cs2_desc: "Current day matches + 3 days ahead",
    games_valorant: "Valorant",
    games_valorant_desc: "Current day matches",
    games_lol: "League of Legends",
    games_lol_desc: "Current day matches",
    games_rocket: "Rocket League",
    games_rocket_desc: "Current day matches",
    games_teams_supported: "Supported teams",
    
    // Features
    features_title: "Why use it?",
    features_subtitle: "Main calendar features",
    feature1_title: "Fully Automatic",
    feature1_desc: "Continuous updates via GitHub Actions",
    feature2_title: "Smart Notifications",
    feature2_desc: "15min reminder before each match",
    feature3_title: "Works Everywhere",
    feature3_desc: "Google Calendar, Outlook and Apple Calendar",
    feature4_title: "Auto Cleanup",
    feature4_desc: "Removes old matches automatically",
    
    // How-to
    howto_title: "How to Add",
    howto_subtitle: "Choose your platform",
    howto_tab_google: "Google",
    howto_tab_outlook: "Outlook",
    howto_tab_apple: "Apple",
    howto_step1: "Copy the URL",
    howto_step2_google: "Open Google Calendar",
    howto_step2_outlook: "Download the .ics",
    howto_step2_apple: "File → New Subscription",
    howto_step3_google: "Add via URL",
    howto_step3_google_desc: 'Click + → "From URL" → Paste',
    howto_step3_outlook: "Open the file",
    howto_step3_outlook_desc: "Double click calendar.ics",
    howto_step3_apple: "Paste and Subscribe",
    howto_step4_outlook: "Save",
    howto_step4_outlook_desc: '"Save & Close"',
    howto_download_btn: '"Download Calendar" button',

    // Footer
    footer_tagline: "Made with ❤️ for the Brazilian esports community",
    footer_opensource: "Open Source",
    footer_github_btn: "View on GitHub",
    footer_contribute: "Contribute to the project",
    footer_last_update: "Last update:",
    footer_copyright: "Otavio Zanon - 2026",
  }
};

// Estado atual do idioma (default: pt)
export let currentLang = localStorage.getItem('language') || 'pt';

// Função para trocar idioma
export function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('language', lang);
}

// Função para pegar tradução
export function t(key) {
  return translations[currentLang][key] || key;
}
