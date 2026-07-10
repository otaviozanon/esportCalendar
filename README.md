# 📅 EsportCalendar

Automatic esports calendar generator in iCalendar format (.ics). Tracks matches from CS2, Valorant, League of Legends, and Rocket League from Brazilian teams.

## 🌐 Live Website

**🔗 Frontend :** [https://otaviozanon.github.io/esportCalendar/](https://otaviozanon.github.io/esportCalendar/)

**📅 Calendar (.ics):** [https://is.gd/EsportCalendar](https://is.gd/EsportCalendar)

## 📖 About

`esportCalendar` is a Python script that automates the creation of iCalendar (.ics) files for esports events. It solves the challenge of manually tracking tournaments and esports matches across different platforms, simplifying the process by scraping data from [tips.gg](https://tips.gg) and generating a calendar file compatible with Google Calendar, Outlook, and Apple Calendar.

**Target audience:** Esports enthusiasts, professional players, teams, and organizations who want to track events without manual entry.

## ✨ Features

- 🎯 **Automatic Generation**: Creates iCalendar (.ics) files from esports event data
- 🌐 **Web Scraping**: Extracts event information from [tips.gg](https://tips.gg) using Bright Data or Scrape.do
- 📅 **iCalendar Format**: Generates calendars in standard format, compatible with any calendar application
- 🎮 **Multiple Esports**: Supports CS2, Valorant, League of Legends, and Rocket League
- 🇧🇷 **Brazilian Teams**: Tracks specific Brazilian teams in each game
- ⚡ **Dual-API Fallback**: Primary: Bright Data (5k/month) → Fallback: Scrape.do (1k/month)
- 🔄 **Smart Scheduling**: CS2 every 50min, others 2x/day (auto-adjusts on API fallback)
- 🪶 **Lightweight**: No heavy dependencies (no Selenium/ChromeDriver)
- 🔔 **Reminders**: Adds alerts 15 minutes before each event

## 🚀 Quick Start

```bash
git clone https://github.com/otaviozanon/esportCalendar.git
cd esportCalendar
pip install -r scripts/requirements.txt
export BRIGHT_DATA_API_KEY="your_key"  # or SCRAPE_DO_API_KEY
python scripts/core/generate_ics.py
```

This will generate a `calendar.ics` file that you can import into your calendar.

## 📦 Installation

### Prerequisites

- Python 3.8+
- [Bright Data](https://brightdata.com) API Key (primary, 5k/month free) OR
- [Scrape.do](https://scrape.do) API Key (fallback, 1k/month free)

### Steps

1. **Clone the repository:**

   ```bash
   git clone https://github.com/otaviozanon/esportCalendar.git
   cd esportCalendar
   ```

2. **Install dependencies:**

   ```bash
   pip install -r scripts/requirements.txt
   ```

3. **Configure API keys:**

   ```bash
   export BRIGHT_DATA_API_KEY="your_brightdata_key"  # Primary
   export SCRAPE_DO_API_KEY="your_scrapedo_key"     # Fallback
   ```

4. **Run the script:**

   ```bash
   python scripts/core/generate_ics.py
   ```

5. **Import the calendar:**
   Open the generated `calendar.ics` file and import it into your favorite calendar application (Google Calendar, Outlook, Apple Calendar, etc).

## ⚙️ Configuration

### Environment Variables

```bash
BRIGHT_DATA_API_KEY  # Bright Data API key (primary, optional)
SCRAPE_DO_API_KEY    # Scrape.do API key (fallback, optional)
```

At least one API key is required. If both are provided, Bright Data is used first with automatic fallback to Scrape.do on errors.

### Customizing Teams

Edit `scripts/core/config.py` to modify `GAMES_CONFIG`:

```python
GAMES_CONFIG = {
    "CS2": GameConfig(
        teams={"FURIA", "paiN Gaming", ...},
        # ...
    ),
}
```

## 🌐 Frontend

The dashboard is built with a modular architecture:

- **GSAP**: High-performance animations
- **Lucide**: Modern icon set
- **Tailwind CSS**: Utility-first styling
- **ical.js**: Live calendar parsing
- **ES6 Modules**: Clean, component-based logic

### Live Calendar

Real-time upcoming matches display:

- Auto-refresh every 5 minutes
- Filter by game (CS2, VAL, LOL, RL)
- Responsive card-based layout
- Grouped by esport with event counts

## 🎯 Execution Logic

### With Bright Data (Primary - 5k req/month)

**CS2:**

- Every 50 minutes (~27x/day)
- Scrapes rotating days (day 0 → 1 → 2)

**Valorant, LOL, RL:**

- 2x per day (06:00 and 18:00)
- Scrapes current day only

### With Scrape.do (Fallback - 1k req/month)

**CS2:**

- 3x per day (06:00, 12:00, 18:00)
- Scrapes rotating days (day 0 → 1 → 2)

**Valorant, LOL, RL:**

- 1x per day (06:00)
- Scrapes current day only

State tracked in `scripts/data/state.json` - automatic API fallback on errors/limits.

## ❓ FAQ

**Q: Why Bright Data/Scrape.do instead of Selenium?**
A: Cloud APIs are faster, more reliable, and don't require heavy ChromeDriver. Bright Data offers 5k free requests/month.

**Q: How do I add new esports?**
A: Add an entry to the `GAMES` dictionary with the tips.gg base_path and desired teams.

**Q: Can I use this offline?**
A: No, the script needs internet access to reach tips.gg via the scraping APIs.

**Q: What timezone is used?**
A: America/Sao_Paulo (BRT)

**Q: How do I import the calendar?**
A: Open the `calendar.ics` file and import it into your calendar (Google Calendar, Outlook, Apple Calendar, etc) || Or if wanna use this calendar, use subscribe calendar: `https://is.gd/EsportCalendar`

## 📝 License

This project is under the MIT License. See the LICENSE file for details.

## 🙏 Acknowledgments

- [tips.gg](https://tips.gg) - Esports data source
- [Bright Data](https://brightdata.com) - Primary web scraping API (5k free/month)
- [Scrape.do](https://scrape.do) - Fallback web scraping API (1k free/month)
- [icalendar](https://github.com/icalendar/icalendar) - .ics file generation
- [requests](https://github.com/psf/requests) - HTTP requests
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [pytz](https://pypi.org/project/pytz/) - Timezone management
